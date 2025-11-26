import requests
import json
from typing import List, Optional
from config import Config
from models import Order, LineItem, CustomAttribute
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
                                        title
                                        selectedOptions {
                                            name
                                            value
                                        }
                                    }
                                    originalUnitPriceSet {
                                        shopMoney {
                                            amount
                                        }
                                    }
                                    customAttributes {
                                        key
                                        value
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
                    variant_data = item.get("variant") or {}
                    selected_options = variant_data.get("selectedOptions") or []
                    size = next(
                        (
                            option.get("value")
                            for option in selected_options
                            if option.get("name", "").lower() == "size"
                        ),
                        None
                    )
                    custom_attributes = [
                        CustomAttribute(key=attr["key"], value=attr["value"])
                        for attr in (item.get("customAttributes") or [])
                    ]

                    line_items.append(LineItem(
                        title=item["title"],
                        quantity=item["quantity"],
                        variant_id=variant_data.get("id", ""),
                        price=item["originalUnitPriceSet"]["shopMoney"]["amount"],
                        size=size,
                        custom_attributes=custom_attributes
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
                                title
                                selectedOptions {
                                    name
                                    value
                                }
                            }
                            originalUnitPriceSet {
                                shopMoney {
                                    amount
                                }
                            }
                            customAttributes {
                                key
                                value
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
                variant_data = item.get("variant") or {}
                selected_options = variant_data.get("selectedOptions") or []
                size = next(
                    (
                        option.get("value")
                        for option in selected_options
                        if option.get("name", "").lower() == "size"
                    ),
                    None
                )
                custom_attributes = [
                    CustomAttribute(key=attr["key"], value=attr["value"])
                    for attr in (item.get("customAttributes") or [])
                ]

                line_items.append(LineItem(
                    title=item["title"],
                    quantity=item["quantity"],
                    variant_id=variant_data.get("id", ""),
                    price=item["originalUnitPriceSet"]["shopMoney"]["amount"],
                    size=size,
                    custom_attributes=custom_attributes
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
    
    def register_webhook(self, topic: str, address: str) -> dict:
        """
        Register a webhook with Shopify
        
        Args:
            topic: The webhook topic (e.g., "orders/create", "orders/updated")
            address: The URL where Shopify should send the webhook
        
        Returns:
            dict: The created webhook data
        """
        mutation = """
        mutation webhookSubscriptionCreate($topic: WebhookSubscriptionTopic!, $webhookSubscription: WebhookSubscriptionInput!) {
            webhookSubscriptionCreate(topic: $topic, webhookSubscription: $webhookSubscription) {
                webhookSubscription {
                    id
                    topic
                    endpoint {
                        __typename
                        ... on WebhookHttpEndpoint {
                            callbackUrl
                        }
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {
            "topic": topic.upper().replace("/", "_"),
            "webhookSubscription": {
                "callbackUrl": address,
                "format": "JSON"
            }
        }
        
        try:
            response = requests.post(
                self.config.shopify_graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to register webhook: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            result = data["data"]["webhookSubscriptionCreate"]
            
            if result["userErrors"]:
                raise Exception(f"User errors: {result['userErrors']}")
            
            return result["webhookSubscription"]
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to register webhook: {str(e)}")
    
    def list_webhooks(self) -> List[dict]:
        """
        List all registered webhooks
        
        Returns:
            List[dict]: List of webhook subscriptions
        """
        query = """
        query {
            webhookSubscriptions(first: 50) {
                edges {
                    node {
                        id
                        topic
                        endpoint {
                            __typename
                            ... on WebhookHttpEndpoint {
                                callbackUrl
                            }
                        }
                        createdAt
                    }
                }
            }
        }
        """
        
        try:
            response = requests.post(
                self.config.shopify_graphql_url,
                headers=self.headers,
                json={"query": query}
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to list webhooks: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            webhooks = []
            for edge in data["data"]["webhookSubscriptions"]["edges"]:
                node = edge["node"]
                webhook = {
                    "id": node["id"],
                    "topic": node["topic"],
                    "callback_url": node["endpoint"].get("callbackUrl", "N/A"),
                    "created_at": node["createdAt"]
                }
                webhooks.append(webhook)
            
            return webhooks
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to list webhooks: {str(e)}")
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a webhook subscription
        
        Args:
            webhook_id: The ID of the webhook to delete
        
        Returns:
            bool: True if successful
        """
        mutation = """
        mutation webhookSubscriptionDelete($id: ID!) {
            webhookSubscriptionDelete(id: $id) {
                deletedWebhookSubscriptionId
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        variables = {"id": webhook_id}
        
        try:
            response = requests.post(
                self.config.shopify_graphql_url,
                headers=self.headers,
                json={"query": mutation, "variables": variables}
            )
            
            if response.status_code != 200:
                raise Exception(f"Failed to delete webhook: {response.status_code} - {response.text}")
            
            data = response.json()
            
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            result = data["data"]["webhookSubscriptionDelete"]
            
            if result["userErrors"]:
                raise Exception(f"User errors: {result['userErrors']}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to delete webhook: {str(e)}")
