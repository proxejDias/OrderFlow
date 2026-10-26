from dataclasses import FrozenInstanceError
from decimal import Decimal
import json

import pytest

from orderflow import (
    CardPayment, DeliveryMethod, ExpressDelivery, KaspiPayment, Order,
    PaymentMethod, Product, StandardDelivery, load_products, save_products,
)


@pytest.mark.parametrize('value', [True, None, [], 'abc', 0, -1, float('nan'), float('inf'), '0.001'])
def test_invalid_price(value):
    with pytest.raises(ValueError):
        Product(1, 'Book', value, 1)


@pytest.mark.parametrize('value', [True, None, '2', 1.5, -1])
def test_invalid_stock(value):
    with pytest.raises(ValueError):
        Product(1, 'Book', 10, value)


@pytest.mark.parametrize('id,name', [(True, 'Book'), (0, 'Book'), (1, ''), (1, None)])
def test_invalid_identity(id, name):
    with pytest.raises(ValueError):
        Product(id, name, 10, 1)


def test_inventory_changes():
    product = Product(1, 'Book', 10, 2)
    product.restock(3)
    product.reduce_stock(2)
    assert product.stock == 3
    for method, value in [(product.restock, True), (product.reduce_stock, 4), (product.reduce_stock, 0)]:
        with pytest.raises(ValueError):
            method(value)
    assert product.stock == 3


@pytest.mark.parametrize('delivery,expected', [(StandardDelivery(), '2000.00'), (ExpressDelivery(), '4500.00')])
def test_delivery_rates(delivery, expected):
    assert delivery.calculate_cost(10) == Decimal(expected)


@pytest.mark.parametrize('distance', [True, 0, -1, None, 'x', float('nan'), float('inf')])
@pytest.mark.parametrize('delivery', [StandardDelivery(), ExpressDelivery()])
def test_invalid_distance(delivery, distance):
    with pytest.raises(ValueError):
        delivery.calculate_cost(distance)


@pytest.mark.parametrize('payment', [CardPayment(), KaspiPayment()])
def test_order_prices_and_paid_totals_remain_fixed(payment):
    product = Product(1, 'Book', '10.25', 5)
    order = Order(1)
    order.add_product(product, 1)
    product.price = 99
    order.add_product(product, 1)
    receipt = order.pay(payment, StandardDelivery(), 2)
    assert order.paid_amount == Decimal('420.50')
    assert order.delivery_cost == Decimal('400.00')
    assert order.calculate_total() == Decimal('20.50')
    assert product.stock == 3
    product.price = 1000
    assert order.calculate_final_total(ExpressDelivery(), 100) == Decimal('420.50')
    assert order.to_dict()['paid_amount'] == '420.50'
    assert order.receipt == receipt
    for action in [lambda: order.pay(payment, StandardDelivery(), 1),
                   lambda: order.add_product(product, 1), order.cancel]:
        with pytest.raises(ValueError):
            action()
    assert product.stock == 3


def test_order_items_are_read_only():
    order = Order(1)
    order.add_product(Product(1, 'Book', 10, 2), 1)
    assert isinstance(order.items, tuple)
    with pytest.raises(FrozenInstanceError):
        order.items[0].quantity = 10


def test_duplicate_ids_and_aggregated_quantity():
    product = Product(1, 'Book', 10, 2)
    order = Order(1)
    order.add_product(product, 1)
    with pytest.raises(ValueError):
        order.add_product(Product(1, 'Other', 20, 10), 1)
    order.add_product(product, 1)
    with pytest.raises(ValueError):
        order.add_product(product, 1)
    assert order.items[0].quantity == 2


def test_inventory_is_rechecked_before_payment():
    product = Product(1, 'Book', 10, 1)
    first, second = Order(1), Order(2)
    for order in (first, second):
        order.add_product(product, 1)
    first.pay(CardPayment(), StandardDelivery(), 1)
    with pytest.raises(ValueError):
        second.pay(CardPayment(), StandardDelivery(), 1)
    assert second.status == 'NEW' and second.paid_amount is None


class DeclinedPayment(PaymentMethod):
    def pay(self, amount):
        raise RuntimeError('Declined')


class InvalidReceiptPayment(PaymentMethod):
    def pay(self, amount):
        return False


@pytest.mark.parametrize('payment,error', [(DeclinedPayment(), RuntimeError), (InvalidReceiptPayment(), ValueError)])
def test_payment_failure_preserves_order_and_inventory(payment, error):
    product = Product(1, 'Book', 10, 2)
    order = Order(1)
    order.add_product(product, 1)
    with pytest.raises(error):
        order.pay(payment, StandardDelivery(), 1)
    assert product.stock == 2
    assert order.status == 'NEW'
    assert order.paid_amount is None and order.receipt is None


def test_empty_and_cancelled_orders():
    order = Order(1)
    with pytest.raises(ValueError):
        order.pay(CardPayment(), StandardDelivery(), 1)
    order.cancel()
    with pytest.raises(ValueError):
        order.add_product(Product(1, 'Book', 10, 1), 1)


def test_abstract_interfaces_cannot_be_instantiated():
    for cls in (PaymentMethod, DeliveryMethod):
        with pytest.raises(TypeError):
            cls()


def test_catalog_round_trip(tmp_path):
    path = tmp_path / 'products.json'
    products = [Product(1, 'Книга', '10.10', 2)]
    save_products(products, path)
    assert load_products(path)[0].to_dict() == products[0].to_dict()
    save_products([], path)
    assert load_products(path) == []


@pytest.mark.parametrize('data', [{}, [{'id': 1}], [dict(id=1, name='Book', price='NaN', stock=1)],
                                  [dict(id=1, name='Book', price=1, stock=1)] * 2])
def test_invalid_catalog(tmp_path, data):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        load_products(path)


def test_invalid_save_preserves_existing_file(tmp_path):
    path = tmp_path / 'products.json'
    product = Product(1, 'Book', 10, 1)
    save_products([product], path)
    original = path.read_bytes()
    with pytest.raises(ValueError):
        save_products([product, product], path)
    assert path.read_bytes() == original


def test_missing_and_malformed_catalog(tmp_path):
    path = tmp_path / 'missing.json'
    with pytest.raises(FileNotFoundError):
        load_products(path)
    path.write_text('{', encoding='utf-8')
    with pytest.raises(json.JSONDecodeError):
        load_products(path)


@pytest.mark.parametrize('quantity', [True, 0, -1, 1.5, '1', None])
def test_invalid_order_quantity(quantity):
    order = Order(1)
    with pytest.raises(ValueError):
        order.add_product(Product(1, 'Book', 10, 2), quantity)
    assert order.items == ()


def test_invalid_delivery_does_not_call_payment():
    class SpyPayment(PaymentMethod):
        called = False

        def pay(self, amount):
            self.called = True
            return 'receipt'

    order = Order(1)
    product = Product(1, 'Book', 10, 2)
    order.add_product(product, 1)
    payment = SpyPayment()
    with pytest.raises(ValueError):
        order.pay(payment, StandardDelivery(), float('nan'))
    assert not payment.called and product.stock == 2 and order.status == 'NEW'
