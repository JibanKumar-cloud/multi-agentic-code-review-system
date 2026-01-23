"""
Account Balance Management
Handles financial transactions and balance updates.
"""

import threading
import time
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Transaction:
    id: str
    account_id: str
    amount: float
    type: str  # 'credit' or 'debit'
    timestamp: datetime


class AccountManager:
    """Manages account balances and transactions."""

    def __init__(self):
        self.balances: Dict[str, float] = {}
        self.transactions: Dict[str, list] = {}
        # BUG: Lock exists but is not used consistently
        self.lock = threading.Lock()

    def create_account(self, account_id: str, initial_balance: float = 0.0):
        """Create a new account."""
        self.balances[account_id] = initial_balance
        self.transactions[account_id] = []

    def get_balance(self, account_id: str) -> Optional[float]:
        """Get current balance for an account."""
        return self.balances.get(account_id)

    def deposit(self, account_id: str, amount: float) -> bool:
        """Deposit money into an account."""
        if account_id not in self.balances:
            return False

        if amount <= 0:
            return False

        # BUG: Race condition - read-modify-write without lock
        current = self.balances[account_id]
        # Simulate some processing time
        time.sleep(0.001)
        self.balances[account_id] = current + amount

        self._record_transaction(account_id, amount, "credit")
        return True

    def withdraw(self, account_id: str, amount: float) -> bool:
        """Withdraw money from an account."""
        if account_id not in self.balances:
            return False

        if amount <= 0:
            return False

        # BUG: Race condition - check-then-act without lock
        current = self.balances[account_id]
        if current < amount:
            return False

        # Simulate processing time
        time.sleep(0.001)
        self.balances[account_id] = current - amount

        self._record_transaction(account_id, amount, "debit")
        return True

    def transfer(self, from_account: str, to_account: str, amount: float) -> bool:
        """Transfer money between accounts."""
        if from_account not in self.balances or to_account not in self.balances:
            return False

        # BUG: Race condition - two separate operations not atomic
        # Another thread could modify balances between these calls
        if self.withdraw(from_account, amount):
            if self.deposit(to_account, amount):
                return True
            else:
                # BUG: Failed deposit but withdrawal already happened
                # Money is lost!
                return False
        return False

    def _record_transaction(self, account_id: str, amount: float, tx_type: str):
        """Record a transaction."""
        tx = Transaction(
            id=f"{account_id}_{datetime.now().timestamp()}",
            account_id=account_id,
            amount=amount,
            type=tx_type,
            timestamp=datetime.now()
        )
        # BUG: Appending to list without lock
        self.transactions[account_id].append(tx)

    def get_total_balance(self) -> float:
        """Get total balance across all accounts."""
        # BUG: Iterating over dict that could be modified
        total = 0.0
        for account_id in self.balances:
            total += self.balances[account_id]
        return total


class InventoryManager:
    """Manages product inventory."""

    def __init__(self):
        self.inventory: Dict[str, int] = {}
        self.reserved: Dict[str, int] = {}

    def add_product(self, product_id: str, quantity: int):
        """Add a product to inventory."""
        if product_id in self.inventory:
            self.inventory[product_id] += quantity
        else:
            self.inventory[product_id] = quantity
            self.reserved[product_id] = 0

    def check_availability(self, product_id: str, quantity: int) -> bool:
        """Check if quantity is available."""
        if product_id not in self.inventory:
            return False

        available = self.inventory[product_id] - self.reserved[product_id]
        return available >= quantity

    def reserve(self, product_id: str, quantity: int) -> bool:
        """Reserve inventory for an order."""
        # BUG: Race condition - check and reserve not atomic
        if not self.check_availability(product_id, quantity):
            return False

        # Another thread could reserve between check and this line
        time.sleep(0.001)  # Simulate processing
        self.reserved[product_id] += quantity
        return True

    def fulfill(self, product_id: str, quantity: int) -> bool:
        """Fulfill a reserved order."""
        if product_id not in self.inventory:
            return False

        # BUG: Race condition in reservation check
        if self.reserved[product_id] < quantity:
            return False

        # BUG: Non-atomic decrement operations
        self.reserved[product_id] -= quantity
        self.inventory[product_id] -= quantity
        return True

    def cancel_reservation(self, product_id: str, quantity: int) -> bool:
        """Cancel a reservation."""
        if product_id not in self.reserved:
            return False

        # BUG: Could go negative if called multiple times
        self.reserved[product_id] -= quantity
        return True


class Counter:
    """Thread-safe counter (but it's not actually thread-safe)."""

    def __init__(self):
        self.value = 0

    def increment(self):
        """Increment the counter."""
        # BUG: Classic race condition
        current = self.value
        time.sleep(0.0001)
        self.value = current + 1

    def decrement(self):
        """Decrement the counter."""
        # BUG: Classic race condition
        current = self.value
        time.sleep(0.0001)
        self.value = current - 1

    def get(self) -> int:
        """Get current value."""
        return self.value


class SessionManager:
    """Manages user sessions."""

    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.session_count = 0

    def create_session(self, user_id: str) -> str:
        """Create a new session."""
        # BUG: Race condition on session_count
        session_id = f"session_{self.session_count}"
        self.session_count += 1

        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        return session_id

    def update_activity(self, session_id: str):
        """Update last activity time."""
        if session_id in self.sessions:
            # BUG: Dict access not thread-safe
            self.sessions[session_id]["last_activity"] = datetime.now()

    def cleanup_stale_sessions(self, max_age_seconds: int = 3600):
        """Remove sessions older than max_age."""
        now = datetime.now()

        # BUG: Modifying dict while iterating
        for session_id, session in self.sessions.items():
            age = (now - session["last_activity"]).total_seconds()
            if age > max_age_seconds:
                del self.sessions[session_id]

    def get_active_sessions(self, user_id: str) -> list:
        """Get all active sessions for a user."""
        # BUG: Dict could be modified during iteration
        return [
            sid for sid, session in self.sessions.items()
            if session["user_id"] == user_id
        ]


# Demonstration of race condition
def demonstrate_race_condition():
    """Show the race condition in action."""
    manager = AccountManager()
    manager.create_account("test", 1000.0)

    def withdraw_thread():
        for _ in range(100):
            manager.withdraw("test", 10)

    threads = [threading.Thread(target=withdraw_thread) for _ in range(5)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # Expected: 1000 - (100 * 10 * 5) = -4000 (should fail) or 0
    # Actual: Could be various positive values due to race condition
    print(f"Final balance: {manager.get_balance('test')}")
