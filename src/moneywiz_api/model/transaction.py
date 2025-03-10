from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import pytest

from moneywiz_api.model.raw_data_handler import RawDataHandler as RDH
from moneywiz_api.model.record import Record
from moneywiz_api.types import ID

ABS_TOLERANCE = 0.001
ABS_TOLERANCE2 = 0.01


@dataclass
class Transaction(Record, ABC):
    """
    ENT: 36
    """

    reconciled: bool

    amount: Decimal
    description: str
    datetime: datetime
    notes: Optional[str]

    def __init__(self, row):
        super().__init__(row)
        self.reconciled = row["ZRECONCILED"] == 1
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.description = row["ZDESC2"]
        self.datetime = RDH.get_datetime(row, "ZDATE1")
        self.notes = row["ZNOTES1"]

        # Fixes

        # Validate
        assert self.reconciled is not None, self.as_dict()
        assert self.amount is not None, self.as_dict()
        assert self.description is not None, self.as_dict()
        assert self.datetime is not None, self.as_dict()
        # self.notes can be None


@dataclass
class DepositTransaction(Transaction):
    """
    ENT: 37
    """

    account: ID
    amount: Decimal  # neg: expense, pos: income
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal  # neg: expense, pos: income
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None, self.as_dict()
        assert self.amount is not None, self.as_dict()
        # self.payee can be None
        assert self.original_currency is not None, self.as_dict()
        assert self.original_amount is not None, self.as_dict()

        assert self.amount * self.original_amount > 0, self.as_dict()  # Same sign
        if self.original_exchange_rate is not None:
            assert self.amount == pytest.approx(
                self.original_amount * self.original_exchange_rate, abs=ABS_TOLERANCE
            ), self.as_dict()


@dataclass
class InvestmentExchangeTransaction(Transaction):
    """
    ENT: 38
    """

    account: ID

    from_investment_holding: ID
    from_symbol: str
    to_investment_holding: ID
    to_symbol: str
    from_number_of_shares: Decimal  # neg
    to_number_of_shares: Decimal  # pos

    fee: Decimal
    original_fee: Decimal  # pos: fee, neg: income?
    original_fee_currency: str

    def __init__(self, row):
        super().__init__(row)

        self.account = row["ZACCOUNT2"]
        self.from_investment_holding = row["ZFROMINVESTMENTHOLDING"]
        self.from_symbol = row["ZFROMSYMBOL"]
        self.to_investment_holding = row["ZTOINVESTMENTHOLDING"]
        self.to_symbol = row["ZTOSYMBOL"]
        self.from_number_of_shares = row["ZFROMNUMBEROFSHARES"]
        self.to_number_of_shares = row["ZTONUMBEROFSHARES"]

        self.fee = RDH.get_decimal(row, "ZFEE2")
        self.original_fee = row["ZORIGINALFEE"]
        self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        # Fixes
        if self.original_fee_currency == self.from_symbol:
            self.from_number_of_shares += self.original_fee
        elif self.original_fee_currency == self.to_symbol:
            self.to_number_of_shares += self.original_fee

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.from_investment_holding is not None
        assert self.from_symbol
        assert self.to_investment_holding is not None
        assert self.to_symbol
        assert self.from_number_of_shares <= 0
        assert self.to_number_of_shares >= 0
        assert self.original_fee is not None
        assert self.original_fee_currency in [self.from_symbol, self.to_symbol]

        if self.fee != 0:
            assert self.original_fee != 0

@dataclass
class InvestmentTransaction(Transaction, ABC):
    """
    ENT: 39
    """

    def __init__(self, row):
        super().__init__(row)


@dataclass
class InvestmentBuyTransaction(InvestmentTransaction):
    """
    ENT: 40
    """

    account: ID
    amount: Decimal

    fee: Decimal

    investment_holding: ID
    number_of_shares: Decimal
    price_per_share: Decimal
    symbol: str

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.fee = RDH.get_decimal(row, "ZFEE2")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_decimal(row, "ZPRICEPERSHARE1")
        self.symbol = row["ZSYMBOL1"]

        # Fixes
        self.fee = max(self.fee, 0)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount <= 0
        assert self.fee is not None
        assert self.fee >= 0
        # Either tiny (close to 0) or positive
        assert (
            abs(self.fee) == pytest.approx(0, abs=ABS_TOLERANCE)
            or self.fee > ABS_TOLERANCE
        )
        assert self.investment_holding is not None
        assert self.number_of_shares is not None
        assert self.number_of_shares > 0
        assert self.price_per_share is not None
        assert self.price_per_share >= 0
        assert -(
            self.number_of_shares * self.price_per_share + self.fee
        ) == pytest.approx(self.amount, abs=ABS_TOLERANCE)
        assert self.symbol is not None


@dataclass
class InvestmentSellTransaction(InvestmentTransaction):
    """
    ENT: 41
    """

    account: ID
    amount: Decimal  # neg: loss after fees, pos: income

    fee: Decimal

    investment_holding: ID
    number_of_shares: Decimal
    price_per_share: Decimal
    symbol: str

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.fee = RDH.get_decimal(row, "ZFEE2")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_decimal(row, "ZPRICEPERSHARE1")
        self.symbol = row["ZSYMBOL1"]

        # Fixes
        self.fee = max(self.fee, 0)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None

        assert self.fee is not None
        assert self.fee >= 0
        # Either tiny (close to 0) or positive
        assert (
            abs(self.fee) == pytest.approx(0, abs=ABS_TOLERANCE)
            or self.fee > ABS_TOLERANCE
        )

        assert self.investment_holding is not None
        assert self.number_of_shares is not None
        assert self.number_of_shares > 0
        assert self.price_per_share is not None
        assert self.price_per_share >= 0
        assert (
            self.number_of_shares * self.price_per_share - self.fee
        ) == pytest.approx(self.amount, abs=ABS_TOLERANCE)
        assert self.symbol is not None


@dataclass
class ReconcileTransaction(Transaction):
    """
    ENT: 42
    """

    account: ID

    reconcile_amount: Decimal | None  # new balance
    reconcile_number_of_shares: Decimal | None  # new balance

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.reconcile_amount = RDH.get_nullable_decimal(row, "ZRECONCILEAMOUNT")
        self.reconcile_number_of_shares = RDH.get_nullable_decimal(
            row, "ZRECONCILENUMBEROFSHARES"
        )

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert (
            self.reconcile_amount is not None
            or self.reconcile_number_of_shares is not None
        )


@dataclass
class RefundTransaction(Transaction):
    """
    ENT: 43
    """

    account: ID
    amount: Decimal
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]

        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount > 0

        assert self.original_currency is not None
        assert self.original_amount is not None
        assert self.original_amount > 0

        if self.original_exchange_rate is not None:
            assert self.amount == pytest.approx(
                self.original_amount * self.original_exchange_rate, abs=ABS_TOLERANCE
            )


@dataclass
class TransferBudgetTransaction(Transaction):
    """
    ENT: 44
    """

    def __init__(self, row):
        super().__init__(row)
        # TODO: Not Implemented


@dataclass
class TransferDepositTransaction(Transaction):
    """
    ENT: 45
    """

    account: ID
    amount: Decimal  # pos: in

    # Have a value only if it's a transfer to a Forex account
    # No fee as it is present only in corresponding TransferWithdrawTransaction
    investment_holding: Optional[ID]
    number_of_shares: Optional[Decimal]
    price_per_share: Optional[Decimal]
    symbol: Optional[str]

    sender_account: ID
    sender_transaction: ID

    original_amount: Decimal  # ATTENTION: sign got fixed
    original_currency: str

    sender_amount: Decimal
    sender_currency: str

    # original_fee: Optional[Decimal]
    # original_fee_currency: Optional[str]

    original_exchange_rate: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_nullable_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_nullable_decimal(row, "ZPRICEPERSHARE1")
        self.symbol = row["ZSYMBOL1"]

        self.sender_account = row["ZSENDERACCOUNT"]
        self.sender_transaction = row["ZSENDERTRANSACTION"]

        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.sender_amount = RDH.get_decimal(row, "ZORIGINALSENDERAMOUNT")
        self.sender_currency = row["ZORIGINALSENDERCURRENCY"]

        # self.original_fee = RDH.get_nullable_decimal(row, "ZORIGINALFEE")
        # self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        self.original_exchange_rate = RDH.get_decimal(row, "ZORIGINALEXCHANGERATE")

        # Fixes
        self.original_amount = abs(self.original_amount)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount > 0
        assert self.sender_account is not None
        assert self.sender_transaction is not None
        assert self.original_amount is not None
        assert self.original_amount > 0
        assert self.original_currency is not None
        assert self.sender_amount is not None
        assert self.sender_amount <= 0
        assert self.sender_currency is not None

        if self.investment_holding is None:
            assert self.amount == pytest.approx(self.original_amount, abs=ABS_TOLERANCE)
        else:
            assert self.number_of_shares is not None
            assert self.price_per_share is not None
            # assert self.original_fee_currency is not None
            assert self.symbol is not None

        assert self.original_amount == pytest.approx(
            -self.sender_amount * self.original_exchange_rate,
            abs=ABS_TOLERANCE,
        )


@dataclass
class TransferWithdrawTransaction(Transaction):
    """
    ENT: 46
    """

    account: ID
    amount: Decimal

    # Have a value only if it's a transfer to a Forex account
    fee: Optional[Decimal]
    investment_holding: Optional[ID]
    number_of_shares: Optional[Decimal]
    price_per_share: Optional[Decimal]
    symbol: Optional[str]

    recipient_account: ID
    recipient_transaction: ID

    original_amount: Decimal  # always neg
    original_currency: str

    recipient_amount: Decimal  # ATTENTION: sign got fixed
    recipient_currency: str

    original_fee: Optional[Decimal]
    original_fee_currency: Optional[str]

    original_exchange_rate: Decimal

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")

        self.fee = RDH.get_nullable_decimal(row, "ZFEE2")

        self.investment_holding = row["ZINVESTMENTHOLDING"]
        self.number_of_shares = RDH.get_nullable_decimal(row, "ZNUMBEROFSHARES1")
        self.price_per_share = RDH.get_nullable_decimal(row, "ZPRICEPERSHARE1")
        self.symbol = row["ZSYMBOL1"]

        self.recipient_account = row["ZRECIPIENTACCOUNT1"]
        self.recipient_transaction = row["ZRECIPIENTTRANSACTION"]

        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_currency = row["ZORIGINALCURRENCY"]
        self.recipient_amount = RDH.get_decimal(row, "ZORIGINALRECIPIENTAMOUNT")
        self.recipient_currency = row["ZORIGINALRECIPIENTCURRENCY"]

        self.original_fee = RDH.get_nullable_decimal(row, "ZORIGINALFEE")
        self.original_fee_currency = row["ZORIGINALFEECURRENCY"]

        self.original_exchange_rate = RDH.get_decimal(row, "ZORIGINALEXCHANGERATE")

        # Fixes
        self.recipient_amount = abs(self.recipient_amount)

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        assert self.amount < 0
        assert self.recipient_account is not None
        assert self.recipient_transaction is not None
        assert self.original_amount is not None
        assert self.original_amount < 0
        assert self.original_currency is not None
        assert self.recipient_amount is not None
        assert self.recipient_amount > 0
        assert self.recipient_currency is not None

        if self.investment_holding is None:
            assert self.amount == self.original_amount
        else:
            assert self.fee is not None
            assert self.number_of_shares is not None
            assert self.price_per_share is not None
            assert self.original_fee_currency is not None
            assert self.symbol is not None

        assert self.original_exchange_rate is not None
        assert self.original_amount == pytest.approx(
            -self.recipient_amount / self.original_exchange_rate,
            abs=ABS_TOLERANCE,
        )


@dataclass
class WithdrawTransaction(Transaction):
    """
    ENT: 47
    """

    account: ID
    amount: Decimal  # neg: expense, pos: income
    payee: Optional[ID]

    # FX
    original_currency: str
    original_amount: Decimal  # neg: expense, pos: income ATTENTION: sign got fixed
    original_exchange_rate: Optional[Decimal]

    def __init__(self, row):
        super().__init__(row)
        self.account = row["ZACCOUNT2"]
        self.amount = RDH.get_decimal(row, "ZAMOUNT1")
        self.payee = row["ZPAYEE2"]

        self.original_currency = row["ZORIGINALCURRENCY"]
        self.original_amount = RDH.get_decimal(row, "ZORIGINALAMOUNT")
        self.original_exchange_rate = RDH.get_nullable_decimal(
            row, "ZORIGINALEXCHANGERATE"
        )

        # Fixes
        if self.amount * self.original_amount < 0:
            self.original_amount = -self.original_amount

        if self.original_exchange_rate == Decimal(0):
            self.original_exchange_rate = None

        # Validate
        self.validate()

    def validate(self):
        assert self.account is not None
        assert self.amount is not None
        # self.payee can be None
        assert self.original_currency is not None
        assert self.original_amount is not None

        assert self.amount * self.original_amount > 0

        if self.original_exchange_rate is not None:
            assert self.amount == pytest.approx(
                self.original_amount * self.original_exchange_rate, abs=ABS_TOLERANCE2
            )
