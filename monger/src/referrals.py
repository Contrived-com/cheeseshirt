"""
Referral network lookup.

The Monger knows his people. This module handles lookups by:
- Name (fuzzy matching, ~80% threshold)
- Email (exact match)
- Phone (exact match, normalized)

Also handles 2nd-degree connections ("friend of a friend").
"""

import json
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher
from dataclasses import dataclass

from .config import get_settings


def get_config():
    """Alias for get_settings for clarity."""
    return get_settings()


@dataclass
class ReferralMatch:
    """Result of a referral lookup."""
    referrer_id: str
    name: str
    nickname: Optional[str]
    tier: str
    discount: int
    purchases: int
    match_type: str  # "direct" or "friend_of"
    match_method: str  # "name", "email", "phone"
    connected_through: Optional[str] = None  # For friend_of matches
    relationship: Optional[str] = None  # e.g., "sister", "coworker"


class ReferralNetwork:
    """The Monger's network of known buyers."""
    
    def __init__(self, data_path: Optional[str] = None):
        config = get_config()
        self.data_path = Path(data_path) if data_path else Path(config.referrals_path)
        self.data: Dict[str, Any] = {}
        self.referrers: Dict[str, Dict] = {}  # id -> referrer
        self._load()
    
    def _load(self):
        """Load referrals data from JSON file."""
        if not self.data_path.exists():
            print(f"Referrals file not found: {self.data_path}")
            return
        
        try:
            with open(self.data_path) as f:
                self.data = json.load(f)
            
            # Index by ID for fast lookup
            for ref in self.data.get("referrers", []):
                self.referrers[ref["id"]] = ref
            
            print(f"Loaded {len(self.referrers)} referrers from {self.data_path}")
        except Exception as e:
            print(f"Error loading referrals: {e}")
    
    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to digits only."""
        return re.sub(r'\D', '', phone)
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison."""
        return name.lower().strip()
    
    def _fuzzy_match(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings are similar enough (80% default)."""
        ratio = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
        return ratio >= threshold
    
    def _get_discount(self, tier: str) -> int:
        """Get discount percentage for a tier."""
        tiers = self.data.get("tiers", {})
        return tiers.get(tier, {}).get("discount", 0)
    
    def lookup_by_email(self, email: str) -> Optional[ReferralMatch]:
        """Look up a referrer by exact email match."""
        email_lower = email.lower().strip()
        
        for ref in self.data.get("referrers", []):
            emails = [e.lower() for e in ref.get("emails", [])]
            if email_lower in emails:
                return ReferralMatch(
                    referrer_id=ref["id"],
                    name=ref["name"],
                    nickname=ref.get("nickname"),
                    tier=ref["tier"],
                    discount=self._get_discount(ref["tier"]),
                    purchases=ref.get("purchases", 0),
                    match_type="direct",
                    match_method="email",
                )
        
        return None
    
    def lookup_by_phone(self, phone: str) -> Optional[ReferralMatch]:
        """Look up a referrer by phone number."""
        phone_normalized = self._normalize_phone(phone)
        
        if len(phone_normalized) < 10:
            return None  # Too short to be valid
        
        for ref in self.data.get("referrers", []):
            for p in ref.get("phones", []):
                if self._normalize_phone(p) == phone_normalized:
                    return ReferralMatch(
                        referrer_id=ref["id"],
                        name=ref["name"],
                        nickname=ref.get("nickname"),
                        tier=ref["tier"],
                        discount=self._get_discount(ref["tier"]),
                        purchases=ref.get("purchases", 0),
                        match_type="direct",
                        match_method="phone",
                    )
        
        return None
    
    def lookup_by_name(self, name: str, threshold: float = 0.8) -> Optional[ReferralMatch]:
        """Look up a referrer by fuzzy name match."""
        name_normalized = self._normalize_name(name)
        
        for ref in self.data.get("referrers", []):
            # Check main name
            if self._fuzzy_match(name_normalized, ref["name"], threshold):
                return ReferralMatch(
                    referrer_id=ref["id"],
                    name=ref["name"],
                    nickname=ref.get("nickname"),
                    tier=ref["tier"],
                    discount=self._get_discount(ref["tier"]),
                    purchases=ref.get("purchases", 0),
                    match_type="direct",
                    match_method="name",
                )
            
            # Check nickname
            nickname = ref.get("nickname")
            if nickname and self._fuzzy_match(name_normalized, nickname, threshold):
                return ReferralMatch(
                    referrer_id=ref["id"],
                    name=ref["name"],
                    nickname=nickname,
                    tier=ref["tier"],
                    discount=self._get_discount(ref["tier"]),
                    purchases=ref.get("purchases", 0),
                    match_type="direct",
                    match_method="name",
                )
        
        return None
    
    def lookup(self, query: str) -> Optional[ReferralMatch]:
        """
        Look up a referrer by any identifier.
        
        Tries in order:
        1. Email (if contains @)
        2. Phone (if mostly digits)
        3. Name (fuzzy match)
        """
        query = query.strip()
        
        if not query:
            return None
        
        # Email?
        if '@' in query:
            return self.lookup_by_email(query)
        
        # Phone? (mostly digits)
        digits = re.sub(r'\D', '', query)
        if len(digits) >= 10 and len(digits) / len(query.replace(' ', '')) > 0.7:
            return self.lookup_by_phone(query)
        
        # Name
        return self.lookup_by_name(query)
    
    def lookup_with_connections(self, query: str) -> Optional[ReferralMatch]:
        """
        Look up a referrer, including 2nd-degree connections.
        
        If direct match found, returns it.
        If no direct match, searches connections of all referrers.
        """
        # Try direct match first
        direct = self.lookup(query)
        if direct:
            return direct
        
        # Search 2nd-degree connections
        # For each referrer, check if query matches any of their relationships
        for ref in self.data.get("referrers", []):
            for rel in ref.get("relationships", []):
                connected_id = rel.get("id")
                connected_ref = self.referrers.get(connected_id)
                
                if not connected_ref:
                    continue
                
                # Check if query matches the connected person
                match = None
                query_lower = query.lower().strip()
                
                # Check email
                if '@' in query:
                    if query_lower in [e.lower() for e in connected_ref.get("emails", [])]:
                        match = connected_ref
                
                # Check name
                elif self._fuzzy_match(query_lower, connected_ref["name"]):
                    match = connected_ref
                
                # Check nickname
                elif connected_ref.get("nickname") and self._fuzzy_match(query_lower, connected_ref["nickname"]):
                    match = connected_ref
                
                if match:
                    # Found a 2nd-degree connection!
                    return ReferralMatch(
                        referrer_id=match["id"],
                        name=match["name"],
                        nickname=match.get("nickname"),
                        tier="friend_of",  # 2nd degree gets friend_of tier
                        discount=self._get_discount("friend_of"),
                        purchases=match.get("purchases", 0),
                        match_type="friend_of",
                        match_method="name" if not '@' in query else "email",
                        connected_through=ref["name"],
                        relationship=rel.get("type"),
                    )
        
        return None
    
    def get_referrer(self, referrer_id: str) -> Optional[Dict]:
        """Get full referrer data by ID."""
        return self.referrers.get(referrer_id)
    
    def add_purchase(self, referrer_id: str) -> bool:
        """
        Increment purchase count for a referrer.
        
        Note: This modifies in-memory data but doesn't persist to disk.
        For persistence, you'd need to implement save().
        """
        if referrer_id not in self.referrers:
            return False
        
        self.referrers[referrer_id]["purchases"] = self.referrers[referrer_id].get("purchases", 0) + 1
        
        # Check for tier upgrades
        purchases = self.referrers[referrer_id]["purchases"]
        current_tier = self.referrers[referrer_id]["tier"]
        
        if purchases >= 10 and current_tier != "ultra":
            self.referrers[referrer_id]["tier"] = "ultra"
        elif purchases >= 5 and current_tier == "buyer":
            self.referrers[referrer_id]["tier"] = "vip"
        
        return True


# Singleton instance
_network: Optional[ReferralNetwork] = None


def get_network() -> ReferralNetwork:
    """Get the referral network singleton."""
    global _network
    if _network is None:
        _network = ReferralNetwork()
    return _network


def lookup_referral(query: str) -> Optional[ReferralMatch]:
    """Convenience function to look up a referral."""
    return get_network().lookup_with_connections(query)

