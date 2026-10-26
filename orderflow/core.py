"""OrderFlow domain model. Payment implementations are local simulations."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def integer(value, label, minimum=1):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def number(value, label, *, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal, str)):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not result.is_finite() or result < 0 or (result == 0 and not allow_zero):
        raise ValueError(f"{label} must be finite and {'non-negative' if allow_zero else 'positive'}")
    return result


def money(value, *, allow_zero=False):
    result = number(value, "Amount", allow_zero=allow_zero)
    try:
        result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Amount is too large") from exc
    if not allow_zero and result == 0:
        raise ValueError("Amount must be at least 0.01")
    return result


class Product:
    def __init__(self, id, name, price, stock):
        self._id = integer(id, "Product ID")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Name must be a non-empty string")
        self._name = name.strip()
        self.price = price
        self.stock = stock

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def price(self):
        return self._price

    @price.setter
    def price(self, value):
        self._price = money(value)

    @property
    def stock(self):
        return self._stock

    @stock.setter
    def stock(self, value):
        self._stock = integer(value, "Stock", 0)

    def restock(self, quantity):
        self.stock += integer(quantity, "Quantity")

    def reduce_stock(self, quantity):
        integer(quantity, "Quantity")
        if quantity > self.stock:
            raise ValueError("Not enough stock")
        self.stock -= quantity

    def to_dict(self):
        return dict(id=self.id, name=self.name, price=str(self.price), stock=self.stock)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"id", "name", "price", "stock"}:
            raise ValueError("Product must contain id, name, price, stock")
        return cls(**data)


class PaymentMethod(ABC):
    @abstractmethod
    def pay(self, amount):
        """Return a receipt string on success; raise an exception on failure."""
        raise NotImplementedError


class KaspiPayment(PaymentMethod):
    def pay(self, amount):
        return f"Paid {money(amount):.2f} KZT via Kaspi"


class CardPayment(PaymentMethod):
    def pay(self, amount):
        return f"Paid {money(amount):.2f} KZT via Card"


class DeliveryMethod(ABC):
    @abstractmethod
    def calculate_cost(self, distance):
        raise NotImplementedError


class StandardDelivery(DeliveryMethod):
    def calculate_cost(self, distance):
        return money(number(distance, "Distance") * 200)


class ExpressDelivery(DeliveryMethod):
    def calculate_cost(self, distance):
        return money(number(distance, "Distance") * 350 + 1000)


@dataclass(frozen=True)
class OrderItem:
    product: Product
    quantity: int
    unit_price: Decimal

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class Order:
    def __init__(self, order_id):
        self._order_id = integer(order_id, "Order ID")
        self._items = []
        self._status = "NEW"
        self._paid_amount = None
        self._delivery_cost = None
        self._receipt = None

    @property
    def order_id(self):
        return self._order_id

    @property
    def items(self):
        return tuple(self._items)

    @property
    def status(self):
        return self._status

    @property
    def paid_amount(self):
        return self._paid_amount

    @property
    def delivery_cost(self):
        return self._delivery_cost

    @property
    def receipt(self):
        return self._receipt

    def _require_new(self):
        if self.status != "NEW":
            raise ValueError("Order must be NEW")

    def add_product(self, product, quantity):
        self._require_new()
        if not isinstance(product, Product):
            raise ValueError("Expected Product")
        integer(quantity, "Quantity")
        for index, item in enumerate(self._items):
            if item.product.id == product.id:
                if item.product is not product:
                    raise ValueError("Different Product objects have the same ID")
                quantity += item.quantity
                if quantity > product.stock:
                    raise ValueError("Not enough stock")
                self._items[index] = OrderItem(product, quantity, item.unit_price)
                return
        if quantity > product.stock:
            raise ValueError("Not enough stock")
        self._items.append(OrderItem(product, quantity, product.price))

    def calculate_total(self):
        return sum((item.subtotal for item in self.items), Decimal("0.00"))

    def calculate_final_total(self, delivery_method, distance):
        if self.status == "PAID":
            return self.paid_amount
        if not isinstance(delivery_method, DeliveryMethod):
            raise ValueError("Expected DeliveryMethod")
        return self.calculate_total() + money(delivery_method.calculate_cost(distance), allow_zero=True)

    def pay(self, payment_method, delivery_method, distance):
        self._require_new()
        if not self.items:
            raise ValueError("Cannot pay empty order")
        if not isinstance(payment_method, PaymentMethod):
            raise ValueError("Expected PaymentMethod")
        for item in self.items:
            if item.quantity > item.product.stock:
                raise ValueError("Not enough stock")
        total = self.calculate_final_total(delivery_method, distance)
        receipt = payment_method.pay(total)
        if not isinstance(receipt, str) or not receipt.strip():
            raise ValueError("Payment must return a non-empty receipt string")
        for item in self.items:
            item.product.reduce_stock(item.quantity)
        self._delivery_cost = total - self.calculate_total()
        self._paid_amount = total
        self._receipt = receipt
        self._status = "PAID"
        return receipt

    def cancel(self):
        self._require_new()
        self._status = "CANCELLED"

    def to_dict(self):
        return {
            "order_id": self.order_id, "status": self.status,
            "items": [dict(product_id=i.product.id, name=i.product.name,
                           quantity=i.quantity, unit_price=str(i.unit_price),
                           subtotal=str(i.subtotal)) for i in self.items],
            "subtotal": str(self.calculate_total()),
            "delivery_cost": None if self.delivery_cost is None else str(self.delivery_cost),
            "paid_amount": None if self.paid_amount is None else str(self.paid_amount),
            "receipt": self.receipt,
        }
