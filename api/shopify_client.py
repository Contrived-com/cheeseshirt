import requests
import json
from typing import List, Optional
from config import Config
from models import Order, LineItem
from datetime import datetime

class ShopifyClient:
    def __init__(self, config: Config):
        self.config = config
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': config.SHOPIFY_ACCESS_TOKEN
        }
    
    def get_orders(self, limit: int = 10, status: str = "any") -> List[Order]:
        """
        Fetch orders from Shopify using GraphQL API
        """
        query = """
        query getOrders($first: Int!, $query: String) {
            orders(first: $first, query: $query, sortKey: CREATED_AT, reverse: true) {
                edges {
                    node {
                        id
                        name
                        email
                        createdAt
                        totalPriceSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        lineItems(first: 50) {
                            edges {
                                node {
                                    title
                                    quantity
                                    variant {
                                        id
                                    }
                                    originalUnitPriceSet {
                                        shopMoney {
                                            amount
                                        }
                                    }
                                }
                            }
                        }
                        shippingAddress {
                            firstName
                            lastName
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
                        }
                        billingAddress {
                            firstName
                            lastName
                            address1
                            address2
                            city
                            province
                            country
                            zip
                            phone
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "first": limit,
            "query": f"status:{status}" if status != "any" else None
        }
        
        try:
            response = requests.post(
                self.config.shopify_graphql_url,
                json={"query": query, "variables": variables},
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            orders = []
            for edge in data["data"]["orders"]["edges"]:
                order_data = edge["node"]
                
                # Parse line items
                line_items = []
                for item_edge in order_data["lineItems"]["edges"]:
                    item = item_edge["node"]
                    line_items.append(LineItem(
                        title=item["title"],
                        quantity=item["quantity"],
                        variant_id=item["variant"]["id"],
                        price=item["originalUnitPriceSet"]["shopMoney"]["amount"]
                    ))
                
                # Parse order
                order = Order(
                    id=order_data["id"],
                    name=order_data["name"],
                    email=order_data["email"],
                    created_at=datetime.fromisoformat(order_data["createdAt"].replace("Z", "+00:00")),
                    total_price=order_data["totalPriceSet"]["shopMoney"]["amount"],
                    currency_code=order_data["totalPriceSet"]["shopMoney"]["currencyCode"],
                    line_items=line_items,
                    shipping_address=order_data.get("shippingAddress"),
                    billing_address=order_data.get("billingAddress")
                )
                orders.append(order)
            
            return orders
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch orders: {str(e)}")
    
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """
        Fetch a specific order by ID
        """
        query = """
        query getOrder($id: ID!) {
            order(id: $id) {
                id
                name
                email
                createdAt
                totalPriceSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                lineItems(first: 50) {
                    edges {
                        node {
                            title
                            quantity
                            variant {
                                id
                            }
                            originalUnitPriceSet {
                                shopMoney {
                                    amount
                                }
                            }
                        }
                    }
                }
                shippingAddress {
                    firstName
                    lastName
                    address1
                    address2
                    city
                    province
                    country
                    zip
                    phone
                }
                billingAddress {
                    firstName
                    lastName
                    address1
                    address2
                    city
                    province
                    country
                    zip
                    phone
                }
            }
        }
        """
        
        variables = {"id": order_id}
        
        try:
            response = requests.post(
                self.config.shopify_graphql_url,
                json={"query": query, "variables": variables},
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            if not data["data"]["order"]:
                return None
            
            order_data = data["data"]["order"]
            
            # Parse line items
            line_items = []
            for item_edge in order_data["lineItems"]["edges"]:
                item = item_edge["node"]
                line_items.append(LineItem(
                    title=item["title"],
                    quantity=item["quantity"],
                    variant_id=item["variant"]["id"],
                    price=item["originalUnitPriceSet"]["shopMoney"]["amount"]
                ))
            
            # Parse order
            order = Order(
                id=order_data["id"],
                name=order_data["name"],
                email=order_data["email"],
                created_at=datetime.fromisoformat(order_data["createdAt"].replace("Z", "+00:00")),
                total_price=order_data["totalPriceSet"]["shopMoney"]["amount"],
                currency_code=order_data["totalPriceSet"]["shopMoney"]["currencyCode"],
                line_items=line_items,
                shipping_address=order_data.get("shippingAddress"),
                billing_address=order_data.get("billingAddress")
            )
            
            return order
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch order: {str(e)}")
