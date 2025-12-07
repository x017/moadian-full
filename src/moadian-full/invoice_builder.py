"""
Invoice Builder for Moadian System
Simplifies invoice creation with proper validation
"""

import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from .tax_id import TaxIdGenerator
from .serial_manager import SerialManager


class InvoiceItem:
    """Represents a single item in an invoice"""
    
    def __init__(
        self,
        sstid: str,              # کد کالا/خدمت (13 رقم)
        sstt: str,               # شرح کالا/خدمت
        fee: int,                # قیمت واحد (ریال)
        am: int = 1,             # تعداد
        mu: str = "164",         # واحد اندازه‌گیری (164 = عدد)
        dis: int = 0,            # تخفیف
        vra: int = 10,           # نرخ مالیات (درصد)
        **kwargs
    ):
        self.sstid = sstid
        self.sstt = sstt
        self.fee = fee
        self.am = am
        self.mu = mu
        self.dis = dis
        self.vra = vra
        self.extra = kwargs
        
        # Validate
        if len(sstid) != 13 or not sstid.isdigit():
            raise ValueError(f"sstid must be 13 digits, got: {sstid}")
    
    def calculate(self) -> Dict[str, int]:
        """Calculate item totals"""
        prdis = self.fee * self.am          # قبل از تخفیف
        dis = self.dis * self.am            # تخفیف
        adis = prdis - dis                  # بعد از تخفیف
        vam = int(adis * self.vra / 100)    # مالیات
        tsstam = adis + vam                 # جمع کل
        
        return {
            "prdis": prdis,
            "dis": dis,
            "adis": adis,
            "vam": vam,
            "tsstam": tsstam
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to invoice body format"""
        calc = self.calculate()
        
        return {
            "sstid": self.sstid,
            "sstt": self.sstt,
            "am": self.am,
            "mu": self.mu,
            "fee": self.fee,
            "cfee": None,
            "cut": None,
            "exr": None,
            "prdis": calc["prdis"],
            "dis": calc["dis"],
            "adis": calc["adis"],
            "vra": self.vra,
            "vam": calc["vam"],
            "odt": None,
            "odr": None,
            "odam": None,
            "olt": None,
            "olr": None,
            "olam": None,
            "consfee": None,
            "spro": None,
            "bros": None,
            "tcpbs": None,
            "cop": None,
            "vop": calc["vam"],
            "bsrn": None,
            "tsstam": calc["tsstam"],
            **self.extra
        }


class InvoiceBuilder:
    """
    Builder class for creating Moadian-compliant invoices
    
    Usage:
        builder = InvoiceBuilder(fiscal_id, seller_tin)
        
        invoice = (builder
            .set_buyer("14011576540", buyer_type=2)
            .add_item(InvoiceItem("2330004219206", "محصول تست", 10000))
            .build())
    """
    
    # Invoice types
    TYPE_SALE = 1           # فروش
    TYPE_SALE_CASH = 2      # فروش نقدی
    TYPE_EXPORT = 3         # صادرات
    TYPE_CONTRACT = 4       # قرارداد
    
    # Invoice patterns
    PATTERN_SALE = 1        # فروش
    PATTERN_RETURN = 2      # برگشت
    PATTERN_CANCEL = 3      # ابطال
    
    # Payment methods
    PAYMENT_CASH = 1        # نقدی
    PAYMENT_CREDIT = 2      # نسیه
    PAYMENT_BOTH = 3        # نقد و نسیه
    
    # Buyer types
    BUYER_LEGAL = 1         # حقوقی
    BUYER_REAL = 2          # حقیقی
    BUYER_FOREIGN = 3       # اتباع غیر ایرانی
    BUYER_PASSPORT = 4      # گذرنامه
    
    def __init__(
        self,
        fiscal_id: str,
        seller_tin: str,
        storage_path: Optional[str] = None
    ):
        """
        Initialize Invoice Builder
        
        Args:
            fiscal_id: 6-character fiscal memory ID (شناسه حافظه مالیاتی)
            seller_tin: 11 or 14 digit seller tax ID (شناسه ملی/کد اقتصادی فروشنده)
            storage_path: Path to store serial history
        """
        # Validate fiscal_id
        if len(fiscal_id) != 6:
            raise ValueError(f"fiscal_id must be 6 characters, got {len(fiscal_id)}")
        
        # Validate seller_tin
        if len(seller_tin) not in [11, 14]:
            raise ValueError(f"seller_tin must be 11 or 14 digits, got {len(seller_tin)}")
        
        self.fiscal_id = fiscal_id.upper()
        self.seller_tin = seller_tin
        
        # Initialize helpers
        self.tax_id_generator = TaxIdGenerator(fiscal_id)
        self.serial_manager = SerialManager(fiscal_id, storage_path)
        
        # Reset builder state
        self._reset()
    
    def _reset(self):
        """Reset builder to initial state"""
        self._items: List[InvoiceItem] = []
        self._buyer_tin: Optional[str] = None
        self._buyer_type: int = self.BUYER_REAL
        self._invoice_type: int = self.TYPE_SALE
        self._invoice_pattern: int = self.PATTERN_SALE
        self._payment_method: int = self.PAYMENT_CASH
        self._invoice_time: Optional[datetime] = None
        self._extra_header: Dict = {}
        self._irtaxid: Optional[str] = None  # For corrections/cancellations
    
    def set_buyer(
        self,
        tin: str,
        buyer_type: int = 2
    ) -> "InvoiceBuilder":
        """
        Set buyer information
        
        Args:
            tin: Buyer tax ID (11 or 14 digits)
            buyer_type: 1=Legal, 2=Individual, 3=Foreign, 4=Passport
            
        Returns:
            self for chaining
        """
        if len(tin) not in [11, 14]:
            raise ValueError(f"Buyer TIN must be 11 or 14 digits, got {len(tin)}")
        
        self._buyer_tin = tin
        self._buyer_type = buyer_type
        return self
    
    def set_invoice_type(
        self,
        invoice_type: int = 1,
        pattern: int = 1
    ) -> "InvoiceBuilder":
        """
        Set invoice type and pattern
        
        Args:
            invoice_type: 1=Sale, 2=Cash Sale, 3=Export, 4=Contract
            pattern: 1=Sale, 2=Return, 3=Cancel
            
        Returns:
            self for chaining
        """
        self._invoice_type = invoice_type
        self._invoice_pattern = pattern
        return self
    
    def set_payment_method(self, method: int = 1) -> "InvoiceBuilder":
        """
        Set payment method
        
        Args:
            method: 1=Cash, 2=Credit, 3=Both
            
        Returns:
            self for chaining
        """
        self._payment_method = method
        return self
    
    def set_invoice_time(self, dt: datetime) -> "InvoiceBuilder":
        """
        Set invoice date/time
        
        Args:
            dt: Invoice datetime
            
        Returns:
            self for chaining
        """
        self._invoice_time = dt
        return self
    
    def set_correction(self, original_tax_id: str) -> "InvoiceBuilder":
        """
        Set this as a correction/cancellation invoice
        
        Args:
            original_tax_id: Tax ID of original invoice being corrected
            
        Returns:
            self for chaining
        """
        self._irtaxid = original_tax_id
        return self
    
    def add_item(self, item: InvoiceItem) -> "InvoiceBuilder":
        """
        Add item to invoice
        
        Args:
            item: InvoiceItem object
            
        Returns:
            self for chaining
        """
        self._items.append(item)
        return self
    
    def add_items(self, items: List[InvoiceItem]) -> "InvoiceBuilder":
        """
        Add multiple items to invoice
        
        Args:
            items: List of InvoiceItem objects
            
        Returns:
            self for chaining
        """
        self._items.extend(items)
        return self
    
    def add_item_dict(
        self,
        sstid: str,
        sstt: str,
        fee: int,
        am: int = 1,
        vra: int = 10,
        **kwargs
    ) -> "InvoiceBuilder":
        """
        Add item using individual parameters
        
        Args:
            sstid: Product code (13 digits)
            sstt: Product name
            fee: Unit price (Rials)
            am: Quantity
            vra: VAT rate (%)
            
        Returns:
            self for chaining
        """
        item = InvoiceItem(sstid=sstid, sstt=sstt, fee=fee, am=am, vra=vra, **kwargs)
        return self.add_item(item)
    
    def set_extra_header(self, **kwargs) -> "InvoiceBuilder":
        """
        Set additional header fields
        
        Returns:
            self for chaining
        """
        self._extra_header.update(kwargs)
        return self
    
    def _calculate_totals(self) -> Dict[str, int]:
        """Calculate invoice totals from items"""
        tprdis = 0  # جمع قبل از تخفیف
        tdis = 0    # جمع تخفیف
        tadis = 0   # جمع بعد از تخفیف
        tvam = 0    # جمع مالیات
        
        for item in self._items:
            calc = item.calculate()
            tprdis += calc["prdis"]
            tdis += calc["dis"]
            tadis += calc["adis"]
            tvam += calc["vam"]
        
        tbill = tadis + tvam  # جمع کل
        
        return {
            "tprdis": tprdis,
            "tdis": tdis,
            "tadis": tadis,
            "tvam": tvam,
            "tbill": tbill
        }
    
    def build(self) -> str:
        """
        Build the invoice JSON
        
        Returns:
            JSON string of complete invoice
        """
        if not self._items:
            raise ValueError("Invoice must have at least one item")
        
        if not self._buyer_tin:
            raise ValueError("Buyer TIN is required")
        
        # Get invoice time
        if self._invoice_time is None:
            self._invoice_time = datetime.now() - timedelta(hours=1)
        
        timestamp = int(self._invoice_time.timestamp() * 1000)
        
        # Get serial
        serial = self.serial_manager.get_next()
        
        # Generate Tax ID
        taxid = self.tax_id_generator.generate(timestamp, serial)
        
        # Generate invoice number
        invoice_number = self.tax_id_generator.get_invoice_number(serial)
        
        # Calculate totals
        totals = self._calculate_totals()
        
        # Build header
        header = {
            "taxid": taxid,
            "indatim": timestamp,
            "indati2m": timestamp,
            "inty": self._invoice_type,
            "inno": invoice_number,
            "irtaxid": self._irtaxid,
            "inp": self._invoice_pattern,
            "ins": 1,  # موضوع: اصلی
            "tins": self.seller_tin,
            "tinb": self._buyer_tin,
            "tob": self._buyer_type,
            "bid": None,
            "sbc": None,
            "bpc": None,
            "bbc": None,
            "ft": None,
            "bpn": None,
            "scln": None,
            "scc": None,
            "crn": None,
            "billid": None,
            "tprdis": totals["tprdis"],
            "tdis": totals["tdis"],
            "tadis": totals["tadis"],
            "tvam": totals["tvam"],
            "todam": 0,
            "tbill": totals["tbill"],
            "setm": self._payment_method,
            "cap": totals["tbill"] if self._payment_method == self.PAYMENT_CASH else None,
            "insp": totals["tadis"],
            "tvop": totals["tvam"],
            "tax17": 0,
            **self._extra_header
        }
        
        # Build body
        body = [item.to_dict() for item in self._items]
        
        # Build invoice
        invoice = {
            "header": header,
            "body": body,
            "payments": []
        }
        
        # Reset for next invoice
        self._reset()
        
        return json.dumps(invoice, ensure_ascii=False)
    
    def build_dict(self) -> Dict:
        """
        Build the invoice as dictionary
        
        Returns:
            Invoice as dictionary
        """
        return json.loads(self.build())
