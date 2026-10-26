"""Run with python -m orderflow. No files are changed."""
from . import Product, Order, KaspiPayment, ExpressDelivery


def main():
    macbook = Product(1, "MacBook", 500000, 10)
    order = Order(101)
    order.add_product(macbook, 2)
    print(order.pay(KaspiPayment(), ExpressDelivery(), 10))
    print(f"Status: {order.status}; remaining stock: {macbook.stock}")


if __name__ == "__main__":
    main()
