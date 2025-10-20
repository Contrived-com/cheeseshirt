import os
import json
from typing import List, Optional
from datetime import datetime
from models import Order, ProcessedOrder, LineItem
from config import Config

class OrderProcessor:
    def __init__(self, config: Config):
        self.config = config
        # Use state/ directory for containerized deployment
        # or fall back to current directory structure for local dev
        base_dir = os.getenv("STATE_DIR", "state") if os.path.exists("state") or os.getenv("STATE_DIR") else "."
        self.processed_orders_dir = os.path.join(base_dir, "processed_orders")
        self.attachments_dir = os.path.join(base_dir, "attachments")
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        os.makedirs(self.processed_orders_dir, exist_ok=True)
        os.makedirs(self.attachments_dir, exist_ok=True)
    
    def process_order(self, order: Order) -> ProcessedOrder:
        """
        Process an order and generate necessary files for the printer
        """
        processing_notes = self._generate_processing_notes(order)
        attachment_path = self._generate_order_summary(order)
        
        processed_order = ProcessedOrder(
            order=order,
            processing_notes=processing_notes,
            attachment_path=attachment_path,
            email_sent=False
        )
        
        # Save processed order data
        self._save_processed_order(processed_order)
        
        return processed_order
    
    def _generate_processing_notes(self, order: Order) -> str:
        """
        Generate processing notes based on order details
        """
        notes = []
        notes.append(f"Order Processing Notes for {order.name}")
        notes.append(f"Customer Email: {order.email}")
        notes.append(f"Order Date: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        notes.append(f"Total: {order.currency_code} {order.total_price}")
        notes.append("")
        
        # Analyze line items for t-shirt specific processing
        tshirt_items = []
        other_items = []
        
        for item in order.line_items:
            if any(keyword in item.title.lower() for keyword in ['shirt', 'tee', 't-shirt', 'tshirt']):
                tshirt_items.append(item)
            else:
                other_items.append(item)
        
        if tshirt_items:
            notes.append("T-SHIRT ITEMS:")
            for item in tshirt_items:
                notes.append(f"  - {item.title} (Qty: {item.quantity})")
                notes.append(f"    Price: {order.currency_code} {item.price} each")
            notes.append("")
        
        if other_items:
            notes.append("OTHER ITEMS:")
            for item in other_items:
                notes.append(f"  - {item.title} (Qty: {item.quantity})")
            notes.append("")
        
        # Add shipping information
        if order.shipping_address:
            notes.append("SHIPPING ADDRESS:")
            addr = order.shipping_address
            notes.append(f"  {addr.get('firstName', '')} {addr.get('lastName', '')}")
            notes.append(f"  {addr.get('address1', '')}")
            if addr.get('address2'):
                notes.append(f"  {addr.get('address2')}")
            notes.append(f"  {addr.get('city', '')}, {addr.get('province', '')} {addr.get('zip', '')}")
            notes.append(f"  {addr.get('country', '')}")
            if addr.get('phone'):
                notes.append(f"  Phone: {addr.get('phone')}")
            notes.append("")
        
        # Add processing instructions
        notes.append("PROCESSING INSTRUCTIONS:")
        notes.append("1. Verify all t-shirt items are in stock")
        notes.append("2. Check design files and specifications")
        notes.append("3. Confirm shipping address is correct")
        notes.append("4. Process payment and prepare for fulfillment")
        notes.append("5. Send confirmation email to customer")
        
        return "\n".join(notes)
    
    def _generate_order_summary(self, order: Order) -> str:
        """
        Generate a JSON summary file for the printer
        """
        filename = f"order_{order.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.attachments_dir, filename)
        
        # Create order summary data
        summary = {
            "order_id": order.id,
            "order_name": order.name,
            "customer_email": order.email,
            "order_date": order.created_at.isoformat(),
            "total_amount": order.total_price,
            "currency": order.currency_code,
            "line_items": [
                {
                    "title": item.title,
                    "quantity": item.quantity,
                    "variant_id": item.variant_id,
                    "price": item.price
                }
                for item in order.line_items
            ],
            "shipping_address": order.shipping_address,
            "billing_address": order.billing_address,
            "processing_timestamp": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return filepath
    
    def _save_processed_order(self, processed_order: ProcessedOrder):
        """
        Save processed order data to file
        """
        filename = f"processed_{processed_order.order.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.processed_orders_dir, filename)
        
        # Convert to dict for JSON serialization
        data = {
            "order": processed_order.order.dict(),
            "processing_notes": processed_order.processing_notes,
            "attachment_path": processed_order.attachment_path,
            "email_sent": processed_order.email_sent,
            "email_sent_at": processed_order.email_sent_at.isoformat() if processed_order.email_sent_at else None,
            "processed_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_processed_orders(self) -> List[ProcessedOrder]:
        """
        Retrieve all processed orders
        """
        processed_orders = []
        
        if not os.path.exists(self.processed_orders_dir):
            return processed_orders
        
        for filename in os.listdir(self.processed_orders_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.processed_orders_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    # Reconstruct ProcessedOrder object
                    order_data = data['order']
                    order = Order(**order_data)
                    
                    processed_order = ProcessedOrder(
                        order=order,
                        processing_notes=data['processing_notes'],
                        attachment_path=data['attachment_path'],
                        email_sent=data['email_sent'],
                        email_sent_at=datetime.fromisoformat(data['email_sent_at']) if data['email_sent_at'] else None
                    )
                    processed_orders.append(processed_order)
                    
                except Exception as e:
                    print(f"Error loading processed order {filename}: {e}")
        
        return processed_orders
