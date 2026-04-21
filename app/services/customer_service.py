"""Customer resolution: find existing customer by channel identifier or create new."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models import ChannelType, Customer, CustomerIdentifier

logger = get_logger(__name__)


class CustomerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_or_create(
        self,
        channel: ChannelType,
        identifier: str,
        full_name: str,
        company: str | None = None,
    ) -> tuple[Customer, bool]:
        """Resolve a customer from a channel identifier.

        Returns (customer, is_new).
        """
        # 1. Look up existing identifier
        stmt = (
            select(CustomerIdentifier)
            .where(
                CustomerIdentifier.channel == channel,
                CustomerIdentifier.identifier == identifier,
            )
        )
        result = await self.session.execute(stmt)
        ci = result.scalar_one_or_none()

        if ci:
            # Load the related customer
            customer_stmt = select(Customer).where(Customer.id == ci.customer_id)
            customer = (await self.session.execute(customer_stmt)).scalar_one()
            logger.info(
                "Resolved existing customer %s via %s:%s",
                customer.id, channel.value, identifier,
            )
            return customer, False

        # 2. No match — create new customer + identifier
        customer = Customer(
            full_name=full_name,
            company=company,
        )
        self.session.add(customer)
        await self.session.flush()  # populate customer.id

        ci = CustomerIdentifier(
            customer_id=customer.id,
            channel=channel,
            identifier=identifier,
            is_primary=True,
        )
        self.session.add(ci)
        await self.session.flush()

        logger.info(
            "Created new customer %s with %s:%s",
            customer.id, channel.value, identifier,
        )
        return customer, True
