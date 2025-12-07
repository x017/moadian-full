"""
Moadian Client - Iranian Tax System Integration
Complete library for sending invoices to Moadian system
"""

import os
import tempfile
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

import requests
from cryptography.hazmat.primitives.serialization import load_pem_private_key, Encoding
from cryptography.x509 import load_pem_x509_certificate

# Patch authlib BEFORE importing anything else from it
import authlib.jose.rfc7515.jws as jws_module

_original_validate = jws_module.JsonWebSignature._validate_crit_headers

def _patched_validate_crit_headers(self, header):
    """Skip validation for 'sigT' header"""
    if 'crit' in header and 'sigT' in header.get('crit', []):
        crit_list = [c for c in header['crit'] if c != 'sigT']
        if not crit_list:
            modified_header = {k: v for k, v in header.items() if k != 'crit'}
            return _original_validate(self, modified_header)
        else:
            modified_header = header.copy()
            modified_header['crit'] = crit_list
            return _original_validate(self, modified_header)
    return _original_validate(self, header)

jws_module.JsonWebSignature._validate_crit_headers = _patched_validate_crit_headers

from .dto import Packet
from .encryption import sign, encrypt
from .settings import *
from .invoice_builder import InvoiceBuilder, InvoiceItem
from .tax_id import TaxIdGenerator
from .serial_manager import SerialManager


class Moadian:
    """
    Main client for Moadian Tax System
    
    Usage:
        moadi = Moadian(fiscal_id, private_key, certificate)
        
        # Using InvoiceBuilder
        builder = moadi.create_invoice_builder(seller_tin)
        invoice = (builder
            .set_buyer("14011576540")
            .add_item(InvoiceItem("2330004219206", "محصول", 10000))
            .build())
        
        result = moadi.send_invoice(invoice)
    """
    
    def __init__(
        self,
        fiscal_id: str,
        private_key: bytes,
        certificate: bytes,
        storage_path: Optional[str] = None
    ):
        """
        Initialize Moadian client
        
        Args:
            fiscal_id: 6-character fiscal memory ID
            private_key: Private key bytes (PEM format)
            certificate: Certificate bytes (PEM format)
            storage_path: Path to store serial history
        """
        if len(fiscal_id) != 6:
            raise ValueError(f"fiscal_id must be 6 characters, got {len(fiscal_id)}")
        
        self.fiscal_id = fiscal_id.upper()
        self.certificate = load_pem_x509_certificate(certificate)
        self.private_key = load_pem_private_key(private_key, password=None)
        self.storage_path = storage_path or os.getcwd()
        
        # Initialize helpers
        self.tax_id_generator = TaxIdGenerator(fiscal_id)
        self.serial_manager = SerialManager(fiscal_id, storage_path)
        
        self._cached_token = None
    
    def get_cert(self) -> str:
        """Get certificate as base64 string"""
        return self.certificate.public_bytes(
            Encoding.PEM).decode().replace(
                "-----BEGIN CERTIFICATE-----", '').replace(
                    "-----END CERTIFICATE-----", '').strip()
    
    def create_invoice_builder(self, seller_tin: str) -> InvoiceBuilder:
        """
        Create an InvoiceBuilder instance
        
        Args:
            seller_tin: Seller's tax ID (11 or 14 digits)
            
        Returns:
            InvoiceBuilder instance
        """
        return InvoiceBuilder(
            fiscal_id=self.fiscal_id,
            seller_tin=seller_tin,
            storage_path=self.storage_path
        )
    
    def generate_tax_id(
        self,
        timestamp_ms: Optional[int] = None,
        serial: Optional[int] = None
    ) -> str:
        """
        Generate a valid Tax ID
        
        Args:
            timestamp_ms: Timestamp in milliseconds
            serial: Serial number
            
        Returns:
            22-character Tax ID
        """
        return self.tax_id_generator.generate(timestamp_ms, serial)
    
    def get_next_serial(self) -> int:
        """Get next unique serial number"""
        return self.serial_manager.get_next()
    
    # ==========================================
    # HTTP Communication
    # ==========================================
    
    def _get_tax_gov_key(self) -> Dict:
        """Get tax system public key (cached)"""
        temp_dir = tempfile.gettempdir()
        filename = "tax_gov_key"
        where_to_find = os.path.join(temp_dir, filename)
        
        # Check cache first
        if os.path.isfile(where_to_find):
            try:
                with open(where_to_find, 'r') as f:
                    k = json.load(f)
                    if "key" in k:
                        return k
            except Exception:
                pass
        
        srv_info = self._get_server_information()
        
        if "publicKeys" not in srv_info or not srv_info["publicKeys"]:
            raise ValueError("No public keys returned from server-information endpoint")
        
        k = srv_info["publicKeys"][0]
        
        # Save for future use
        try:
            with open(where_to_find, 'w') as f:
                json.dump(k, f)
        except Exception:
            pass
        
        return k
    
    def _prepare_tax_gov_key(self) -> str:
        """Prepare public key in PEM format"""
        server_public_key = self._get_tax_gov_key()["key"]
        return f"-----BEGIN PUBLIC KEY-----\n{server_public_key}\n-----END PUBLIC KEY-----"
    
    def _send_http_request(
        self,
        url: str,
        method: str = "get",
        headers: Optional[Dict] = None,
        need_token: bool = True,
        **kwargs
    ) -> Any:
        """Send HTTP request to Moadian API"""
        if headers is None:
            headers = {}
        
        if need_token:
            token = self._get_token()
            headers["Authorization"] = f"Bearer {token}"
        
        if "Content-Type" not in headers:
            headers["Accept"] = "application/json"
        
        try:
            response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_body = ""
            try:
                error_body = e.response.text
            except:
                pass
            raise Exception(f"HTTP Error: {e}. Details: {error_body}")
    
    def _get_token(self) -> str:
        """Get authentication token"""
        try:
            result = self._send_http_request(NONCE_URL, need_token=False)
        except Exception as e:
            raise Exception(f"Failed to get nonce from {NONCE_URL}: {e}")
        
        if "nonce" not in result:
            raise ValueError(f"Invalid nonce response: {result}")
        
        payload = json.dumps({
            "nonce": result["nonce"],
            "clientId": self.fiscal_id
        })
        jwt = sign(payload, self.private_key, self.get_cert())
        return jwt
    
    def _get_server_information(self) -> Dict:
        """Get server information including public keys"""
        temp_dir = tempfile.gettempdir()
        cache_file = os.path.join(temp_dir, "tax_gov_key")
        
        try:
            return self._send_http_request(SERVER_INFORMATION_URL, need_token=True)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in [401, 403]:
                try:
                    return self._send_http_request(SERVER_INFORMATION_URL, need_token=False)
                except:
                    pass
            if os.path.exists(cache_file):
                try:
                    os.remove(cache_file)
                except:
                    pass
            raise
    
    # ==========================================
    # Invoice Operations
    # ==========================================
    
    def send_invoice(self, invoice: str) -> Dict:
        """
        Send invoice to Moadian system
        
        Args:
            invoice: JSON string of invoice
            
        Returns:
            API response
        """
        server_public_key = self._prepare_tax_gov_key()
        signed_invoice = sign(invoice, self.private_key, self.get_cert())
        encrypted_invoice = encrypt(signed_invoice, server_public_key)
        packets = [Packet(encrypted_invoice, self.fiscal_id).build()]
        headers = {"Content-Type": "application/json"}
        return self._send_http_request(INVOICE_URL, "post", headers, data=json.dumps(packets))
    
    def send_invoice_simple(
        self,
        seller_tin: str,
        buyer_tin: str,
        items: List[Dict],
        buyer_type: int = 2,
        payment_method: int = 1
    ) -> Dict:
        """
        Simplified invoice sending
        
        Args:
            seller_tin: Seller tax ID
            buyer_tin: Buyer tax ID
            items: List of item dicts with keys: sstid, sstt, fee, am, vra
            buyer_type: 1=Legal, 2=Individual
            payment_method: 1=Cash, 2=Credit
            
        Returns:
            API response with UID
        """
        builder = self.create_invoice_builder(seller_tin)
        builder.set_buyer(buyer_tin, buyer_type)
        builder.set_payment_method(payment_method)
        
        for item in items:
            builder.add_item_dict(**item)
        
        invoice = builder.build()
        return self.send_invoice(invoice)
    
    def check_status(self, uid: str, wait_seconds: int = 5) -> Dict:
        """
        Check invoice status
        
        Args:
            uid: Invoice UID
            wait_seconds: Seconds to wait before checking
            
        Returns:
            Status result
        """
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        
        result = self.inquiry_by_uid([uid])
        
        if isinstance(result, list) and result:
            return result[0]
        return {"status": "UNKNOWN"}
    
    # ==========================================
    # Inquiry Methods
    # ==========================================
    
    def inquiry(
        self,
        status: Literal["SUCCESS", "FAILED", "TIMEOUT", "IN_PROGRESS"] = None,
        page_num: int = 1,
        page_size: int = 10
    ) -> Dict:
        """Get list of invoices with optional status filter"""
        params = {
            "pageNumber": page_num,
            "pageSize": page_size,
        }
        if status:
            params["status"] = status
        return self._send_http_request(INQUIRY_URL, params=params)
    
    def inquiry_by_reference_id(self, reference_ids: List[str]) -> List:
        """Inquiry invoices by reference IDs"""
        params = {"referenceIds": reference_ids}
        return self._send_http_request(INQUIRY_BY_REFERENCE_ID_URL, params=params)
    
    def inquiry_by_uid(self, uid_list: List[str]) -> List:
        """Inquiry invoices by UID list"""
        params = {
            "uidList": uid_list,
            "fiscalId": self.fiscal_id
        }
        return self._send_http_request(INQUIRY_BY_UID_URL, params=params)
    
    def get_fiscal_information(self) -> Dict:
        """Get fiscal memory information"""
        params = {"memoryId": self.fiscal_id}
        return self._send_http_request(FISCAL_INFORMATION_URL, params=params)
    
    def get_tax_payer(self, economic_code: str) -> Dict:
        """Get taxpayer information by economic code"""
        params = {"economicCode": economic_code}
        return self._send_http_request(TAXPAYER_URL, params=params)
