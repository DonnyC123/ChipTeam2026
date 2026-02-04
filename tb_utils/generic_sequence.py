from typing import Generic, TypeVar

from tb_utils.abstract_transactions import AbstractTransaction

SequenceItem = TypeVar("SequenceItem", bound=AbstractTransaction)


class GenericSequence(Generic[SequenceItem]):
    def __init__(self, driver, *subscribers):
        self.driver = driver
        self.transaction_subscribers = [s for s in subscribers if hasattr(s, "notify")]

    def add_subscriber(self, *subscribers):
        self.transaction_subscribers.extend(subscribers)

    async def add_transaction(self, transaction: SequenceItem):
        await self.driver.send(transaction)

    async def notify_subscribers(self, transaction):
        for sub in self.transaction_subscribers:
            if hasattr(sub, "notify"):
                await sub.notify(transaction)

            else:
                print(f"Warning: Don't know how to notify {sub}")
