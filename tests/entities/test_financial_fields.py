from decimal import Decimal

from app.domain.entities import (
    AdvancePayment,
    Amount,
    Payment,
    PaymentList,
    TotalAmount,
    Vat,
)


def make_payment(
    *,
    amount: str | None = None,
    vat_amount: str | None = None,
    rate: str | None = None,
    include_vat: bool | None = False,
) -> Payment:
    return Payment(
        amount=(
            Amount(value=Decimal(amount), transcription=None)
            if amount is not None
            else None
        ),
        vat=Vat(
            amount=(
                Amount(value=Decimal(vat_amount), transcription=None)
                if vat_amount is not None
                else None
            ),
            rate=Decimal(rate) if rate is not None else None,
        ),
        include_vat=include_vat,
    )


def test_amount_value_returns_none_when_amount_missing():
    payment = make_payment(amount=None)
    assert payment.amount_value is None


def test_amount_value_returns_decimal_when_present():
    payment = make_payment(amount="1909306.73")
    assert payment.amount_value == Decimal("1909306.73")


def test_vat_amount_value_returns_none_when_vat_amount_missing():
    payment = make_payment(amount="1000.00")
    assert payment.vat_amount_value is None


def test_vat_amount_value_returns_decimal_when_present():
    payment = make_payment(amount="1000.00", vat_amount="166.67")
    assert payment.vat_amount_value == Decimal("166.67")


def test_vat_rate_returns_rate():
    payment = make_payment(rate="20.00")
    assert payment.vat_rate == Decimal("20.00")


def test_expected_vat_amount_none_when_amount_missing():
    payment = make_payment(amount=None, rate="20.00")
    assert payment.expected_vat_amount is None


def test_expected_vat_amount_none_when_rate_missing():
    payment = make_payment(amount="1000.00", rate=None)
    assert payment.expected_vat_amount is None


def test_expected_vat_amount_included_extracts_from_gross():
    payment = make_payment(amount="120.00", rate="20", include_vat=True)
    assert payment.expected_vat_amount == Decimal(20)


def test_expected_vat_amount_excluded_adds_on_top():
    payment = make_payment(amount="100.00", rate="20", include_vat=False)
    assert payment.expected_vat_amount == Decimal(20)


def test_expected_vat_amount_none_when_include_vat_unknown():
    payment = make_payment(amount="100.00", rate="20", include_vat=None)
    assert payment.expected_vat_amount is None


def test_expected_vat_amount_none_when_included_denominator_zero():
    payment = make_payment(amount="100.00", rate="-100", include_vat=True)
    assert payment.expected_vat_amount is None


def test_payment_list_iterates_in_order():
    first = make_payment(amount="100.00")
    second = make_payment(amount="200.00")
    payment_list = PaymentList([first, second])
    assert list(payment_list) == [first, second]


def test_payment_list_len_and_bool():
    assert len(PaymentList([])) == 0
    assert not PaymentList([])
    assert len(PaymentList([make_payment(amount="1.00")])) == 1
    assert PaymentList([make_payment(amount="1.00")])


def test_payment_list_amount_value_none_when_empty():
    assert PaymentList([]).amount_value is None


def test_payment_list_amount_value_sums_present_and_skips_missing():
    payment_list = PaymentList(
        [
            make_payment(amount="318217.79"),
            make_payment(amount=None),
            make_payment(amount="1591088.94"),
        ]
    )
    assert payment_list.amount_value == Decimal("1909306.73")


def test_payment_list_vat_rates_collects_distinct_non_none():
    payment_list = PaymentList(
        [
            make_payment(rate="20.00"),
            make_payment(rate="10.00"),
            make_payment(rate="20.00"),
            make_payment(rate=None),
        ]
    )
    assert payment_list.vat_rates == {Decimal("20.00"), Decimal("10.00")}


def test_payment_list_combined_none_when_empty():
    assert PaymentList([]).combined is None


def test_payment_list_combined_none_when_all_fields_missing():
    payment_list = PaymentList([make_payment(amount=None, vat_amount=None, rate=None)])
    assert payment_list.combined is None


def test_payment_list_combined_sums_amounts_and_keeps_common_rate():
    payment_list = PaymentList(
        [
            make_payment(
                amount="1000.00", vat_amount="166.67", rate="20.00", include_vat=True
            ),
            make_payment(
                amount="2000.00", vat_amount="333.33", rate="20.00", include_vat=True
            ),
        ]
    )
    combined = payment_list.combined
    assert combined is not None
    assert combined.amount_value == Decimal("3000.00")
    assert combined.vat_amount_value == Decimal("500.00")
    assert combined.vat_rate == Decimal("20.00")
    assert combined.include_vat is True


def test_payment_list_combined_drops_rate_when_rates_differ():
    payment_list = PaymentList(
        [
            make_payment(amount="1000.00", rate="20.00"),
            make_payment(amount="2000.00", rate="10.00"),
        ]
    )
    combined = payment_list.combined
    assert combined is not None
    assert combined.vat_rate is None


def test_total_amount_tax_payments_wraps_taxes():
    taxes = [make_payment(amount="100.00"), make_payment(amount="200.00")]
    total_amount = TotalAmount(total=make_payment(amount="300.00"), taxes=taxes)
    tax_payments = total_amount.tax_payments
    assert isinstance(tax_payments, PaymentList)
    assert tax_payments.amount_value == Decimal("300.00")


def make_advance(*, total: Payment | None, payments: list[Payment]) -> AdvancePayment:
    return AdvancePayment(percent=None, total=total, payments=payments)


def test_advance_payment_lines_wraps_payments():
    payments = [make_payment(amount="500.00")]
    advance = make_advance(total=None, payments=payments)
    assert isinstance(advance.payment_lines, PaymentList)
    assert advance.payment_lines.amount_value == Decimal("500.00")


def test_resolved_total_returns_total_when_it_has_amount():
    total = make_payment(amount="954653.36")
    advance = make_advance(total=total, payments=[make_payment(amount="1.00")])
    assert advance.resolved_total is total


def test_resolved_total_falls_back_to_lines_when_total_amount_missing():
    total = make_payment(amount=None, rate="20.00")
    advance = make_advance(
        total=total,
        payments=[make_payment(amount="400.00"), make_payment(amount="600.00")],
    )
    resolved = advance.resolved_total
    assert resolved is not None
    assert resolved.amount_value == Decimal("1000.00")


def test_resolved_total_uses_lines_when_total_missing():
    advance = make_advance(
        total=None,
        payments=[make_payment(amount="400.00"), make_payment(amount="600.00")],
    )
    resolved = advance.resolved_total
    assert resolved is not None
    assert resolved.amount_value == Decimal("1000.00")


def test_resolved_total_none_when_nothing_present():
    advance = make_advance(total=None, payments=[])
    assert advance.resolved_total is None


def test_resolved_total_keeps_total_when_lines_have_no_amount():
    total = make_payment(amount=None, rate="20.00")
    advance = make_advance(total=total, payments=[])
    assert advance.resolved_total is total
