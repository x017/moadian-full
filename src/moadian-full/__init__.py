
"""
Moadian2 - Iranian Tax System (Moadian) Integration Library

Usage:
    from moadian2 import Moadian, InvoiceBuilder, InvoiceItem
    
    # Initialize client
    moadi = Moadian(fiscal_id, private_key, certificate)
    
    # Create invoice using builder
    builder = moadi.create_invoice_builder(seller_tin)
    invoice = (builder
        .set_buyer(buyer_tin)
        .add_item(InvoiceItem("2330004219206", "محصول تست", 10000))
        .build())
    
    # Send invoice
    result = moadi.send_invoice(invoice)
    
    # Check status
    status = moadi.check_status(result['result'][0]['uid'])
"""

from .main import Moadian
from .invoice_builder import InvoiceBuilder, InvoiceItem
from .tax_id import TaxIdGenerator
from .serial_manager import SerialManager
from .verhoeff import Verhoeff

__version__ = "2.0.0"
__all__ = [
    "Moadian",
    "InvoiceBuilder",
    "InvoiceItem",
    "TaxIdGenerator",
    "SerialManager",
    "Verhoeff"
]
