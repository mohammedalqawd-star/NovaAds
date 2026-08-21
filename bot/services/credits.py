from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreditReservation:
    user_id: int
    amount: int
    committed: bool = False


class InsufficientCredits(Exception):
    pass


class CreditService:
    """Business-rule layer; persistence must be supplied by the repository layer."""

    def __init__(self, repository):
        self.repository = repository

    async def reserve(self, user_id: int, amount: int) -> CreditReservation:
        if amount <= 0:
            raise ValueError("amount must be positive")
        async with self.repository.transaction():
            balance = await self.repository.get_balance_for_update(user_id)
            if balance < amount:
                raise InsufficientCredits
            await self.repository.debit(user_id, amount)
        return CreditReservation(user_id=user_id, amount=amount)

    async def refund(self, reservation: CreditReservation) -> None:
        if reservation.committed:
            return
        async with self.repository.transaction():
            await self.repository.credit(reservation.user_id, reservation.amount)
