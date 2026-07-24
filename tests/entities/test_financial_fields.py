from decimal import Decimal

from app.domain.entities import (
    AdvancePayment,
    Money,
    MoneyValidationMode,
    Payment,
    PaymentList,
    TotalAmount,
    Vat,
    VatInclusion,
)
from app.domain.entities.errors.checks import (
    AmountNotPositiveError,
    VatRateNotPositiveError,
)
from app.domain.entities.single_supplier_fields import select_common_vat_inclusion


def make_payment(
    *,
    amount: str | None = None,
    vat_amount: str | None = None,
    rate: str | None = None,
    include_vat: VatInclusion = VatInclusion.EXCLUDED,
) -> Payment:
    return Payment(
        amount=(
            Money(value=Decimal(amount), transcription=None)
            if amount is not None
            else None
        ),
        vat=Vat(
            amount=(
                Money(value=Decimal(vat_amount), transcription=None)
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
    payment = make_payment(
        amount="120.00", rate="20", include_vat=VatInclusion.INCLUDED
    )
    assert payment.expected_vat_amount == Decimal(20)


def test_expected_vat_amount_excluded_adds_on_top():
    payment = make_payment(
        amount="100.00", rate="20", include_vat=VatInclusion.EXCLUDED
    )
    assert payment.expected_vat_amount == Decimal(20)


def test_expected_vat_amount_none_when_include_vat_unknown():
    payment = make_payment(
        amount="100.00", rate="20", include_vat=VatInclusion.UNSPECIFIED
    )
    assert payment.expected_vat_amount is None


def test_expected_vat_amount_none_when_included_denominator_zero():
    payment = make_payment(
        amount="100.00", rate="-100", include_vat=VatInclusion.INCLUDED
    )
    assert payment.expected_vat_amount is None


def test_amount_excluding_vat_uses_rate_when_present():
    payment = make_payment(
        amount="120.00", rate="20", include_vat=VatInclusion.INCLUDED
    )
    assert payment.amount_excluding_vat == Decimal("100.00")


def test_amount_excluding_vat_falls_back_to_vat_amount_when_rate_missing():
    payment = make_payment(
        amount="120.00", vat_amount="20.00", include_vat=VatInclusion.INCLUDED
    )
    assert payment.amount_excluding_vat == Decimal("100.00")


def test_amount_excluding_vat_none_when_rate_and_vat_amount_missing():
    payment = make_payment(amount="120.00", include_vat=VatInclusion.INCLUDED)
    assert payment.amount_excluding_vat is None


def test_amount_including_vat_uses_rate_when_present():
    payment = make_payment(
        amount="100.00", rate="20", include_vat=VatInclusion.EXCLUDED
    )
    assert payment.amount_including_vat == Decimal("120.00")


def test_amount_including_vat_falls_back_to_vat_amount_when_rate_missing():
    payment = make_payment(
        amount="100.00", vat_amount="20.00", include_vat=VatInclusion.EXCLUDED
    )
    assert payment.amount_including_vat == Decimal("120.00")


def test_amount_including_vat_none_when_rate_and_vat_amount_missing():
    payment = make_payment(amount="100.00", include_vat=VatInclusion.EXCLUDED)
    assert payment.amount_including_vat is None


def test_money_add_sums_present_values_and_drops_transcription():
    left = Money(value=Decimal("10.00"), transcription="десять")
    right = Money(value=Decimal("5.00"), transcription="пять")

    result = left + right

    assert result.value == Decimal("15.00")
    assert result.transcription is None


def test_money_add_keeps_other_value_when_one_side_missing():
    left = Money(value=None, transcription=None)
    right = Money(value=Decimal("5.00"), transcription=None)

    assert (left + right).value == Decimal("5.00")


def test_vat_add_sums_amounts_and_keeps_matching_rate():
    left = Vat(
        amount=Money(value=Decimal("10.00"), transcription=None), rate=Decimal(20)
    )
    right = Vat(
        amount=Money(value=Decimal("5.00"), transcription=None), rate=Decimal(20)
    )

    result = left + right

    assert result.amount_value == Decimal("15.00")
    assert result.rate == Decimal(20)


def test_vat_add_drops_rate_when_rates_differ():
    left = Vat(amount=None, rate=Decimal(20))
    right = Vat(amount=None, rate=Decimal(10))

    assert (left + right).rate is None


def test_vat_add_drops_rate_when_only_one_side_has_rate():
    left = Vat(amount=None, rate=Decimal(20))
    right = Vat(amount=None, rate=None)

    assert (left + right).rate is None


def test_select_common_vat_inclusion_unspecified_when_no_amounts():
    payments = [make_payment(amount=None), make_payment(amount=None)]

    assert select_common_vat_inclusion(payments) is VatInclusion.UNSPECIFIED


def test_select_common_vat_inclusion_returns_shared_value_when_homogeneous():
    payments = [
        make_payment(amount="10.00", include_vat=VatInclusion.EXCLUDED),
        make_payment(amount="20.00", include_vat=VatInclusion.EXCLUDED),
    ]

    assert select_common_vat_inclusion(payments) is VatInclusion.EXCLUDED


def test_select_common_vat_inclusion_converts_to_included_when_possible():
    payments = [
        make_payment(amount="120.00", rate="20", include_vat=VatInclusion.INCLUDED),
        make_payment(amount="50.00", rate="20", include_vat=VatInclusion.EXCLUDED),
    ]

    assert select_common_vat_inclusion(payments) is VatInclusion.INCLUDED


def test_select_common_vat_inclusion_falls_back_to_mixed():
    payments = [
        make_payment(amount="100.00", include_vat=VatInclusion.INCLUDED),
        make_payment(amount="50.00", include_vat=VatInclusion.EXCLUDED),
    ]

    assert select_common_vat_inclusion(payments) is VatInclusion.MIXED


def test_payment_add_sums_amount_value_directly_when_homogeneous():
    left = make_payment(amount="100.00", include_vat=VatInclusion.EXCLUDED)
    right = make_payment(amount="50.00", include_vat=VatInclusion.EXCLUDED)

    result = left + right

    assert result.amount_value == Decimal("150.00")
    assert result.include_vat == VatInclusion.EXCLUDED


def test_payment_add_converts_to_common_inclusion_when_rates_allow():
    included = make_payment(
        amount="120.00", rate="20", include_vat=VatInclusion.INCLUDED
    )
    excluded = make_payment(
        amount="50.00", rate="20", include_vat=VatInclusion.EXCLUDED
    )

    result = included + excluded

    assert result.include_vat == VatInclusion.INCLUDED
    assert result.amount_value == Decimal("180.00")


def test_payment_add_keeps_rate_when_both_sides_agree():
    left = make_payment(amount="100.00", rate="20", include_vat=VatInclusion.EXCLUDED)
    right = make_payment(amount="50.00", rate="20", include_vat=VatInclusion.EXCLUDED)

    assert (left + right).vat.rate == Decimal(20)


def test_payment_add_drops_rate_when_rates_differ():
    left = make_payment(amount="100.00", rate="20", include_vat=VatInclusion.EXCLUDED)
    right = make_payment(amount="50.00", rate="10", include_vat=VatInclusion.EXCLUDED)

    assert (left + right).vat.rate is None


def test_payment_add_keeps_other_amount_when_self_amount_missing():
    left = make_payment(amount=None, include_vat=VatInclusion.UNSPECIFIED)
    right = make_payment(amount="50.00", include_vat=VatInclusion.EXCLUDED)

    assert (left + right).amount_value == Decimal("50.00")


def test_payment_add_drops_transcription():
    left = Payment(
        amount=Money(value=Decimal("100.00"), transcription="сто"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )
    right = Payment(
        amount=Money(value=Decimal("50.00"), transcription="пятьдесят"),
        vat=Vat(amount=None, rate=None),
        include_vat=VatInclusion.EXCLUDED,
    )

    assert (left + right).amount.transcription is None


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
                amount="1000.00",
                vat_amount="166.67",
                rate="20.00",
                include_vat=VatInclusion.INCLUDED,
            ),
            make_payment(
                amount="2000.00",
                vat_amount="333.33",
                rate="20.00",
                include_vat=VatInclusion.INCLUDED,
            ),
        ]
    )
    combined = payment_list.combined
    assert combined is not None
    assert combined.amount_value == Decimal("3000.00")
    assert combined.vat_amount_value == Decimal("500.00")
    assert combined.vat_rate == Decimal("20.00")
    assert combined.include_vat is VatInclusion.INCLUDED


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
    taxes = PaymentList([make_payment(amount="100.00"), make_payment(amount="200.00")])
    total_amount = TotalAmount(total=make_payment(amount="300.00"), taxes=taxes)
    tax_payments = total_amount.taxes
    assert isinstance(tax_payments, PaymentList)
    assert tax_payments.amount_value == Decimal("300.00")


def make_advance(*, total: Payment | None, payments: PaymentList) -> AdvancePayment:
    return AdvancePayment(percent=None, total=total, payments=payments)


def test_advance_payment_lines_wraps_payments():
    payments = PaymentList([make_payment(amount="500.00")])
    advance = make_advance(total=None, payments=payments)
    assert isinstance(advance.payments, PaymentList)
    assert advance.payments.amount_value == Decimal("500.00")


# ---------- Money ----------


def test_money_is_correct_accepts_positive_value():
    money = Money(value=Decimal(100), transcription=None)

    assert money.validate() == []


def test_money_is_correct_rejects_zero_by_default():
    money = Money(value=Decimal(0), transcription=None)

    errors = money.validate()

    assert len(errors) == 1
    assert isinstance(errors[0], AmountNotPositiveError)


def test_money_is_correct_allows_zero_when_include_zero():
    money = Money(value=Decimal(0), transcription=None)

    assert money.validate(MoneyValidationMode.NON_NEGATIVE) == []


def test_money_is_correct_rejects_negative():
    money = Money(value=Decimal(-1), transcription=None)

    errors = money.validate()

    assert len(errors) == 1
    assert isinstance(errors[0], AmountNotPositiveError)


# ---------- Vat ----------


def test_vat_is_correct_returns_rate_and_amount_errors():
    vat = Vat(
        amount=Money(value=Decimal(-10), transcription=None),
        rate=Decimal(-20),
    )

    errors = vat.validate()

    assert any(isinstance(e, VatRateNotPositiveError) for e in errors)
    assert any(isinstance(e, AmountNotPositiveError) for e in errors)


# ---------- Payment ----------


def test_payment_is_correct_collects_errors_from_amount_and_vat():
    payment = Payment(
        amount=Money(value=Decimal(-100), transcription=None),
        vat=Vat(
            amount=Money(value=Decimal(-20), transcription=None),
            rate=Decimal(-20),
        ),
        include_vat=VatInclusion.INCLUDED,
    )

    errors = payment.validate()

    assert len(errors) == 3  # noqa: PLR2004
    assert sum(isinstance(e, AmountNotPositiveError) for e in errors) == 2  # noqa: PLR2004
    assert sum(isinstance(e, VatRateNotPositiveError) for e in errors) == 1


# ---------- PaymentList ----------


def test_payment_list_is_correct_collects_errors_from_all_payments():
    payment_list = PaymentList(
        [
            make_payment(amount="100"),
            Payment(
                amount=Money(value=Decimal(-1), transcription=None),
                vat=Vat(amount=None, rate=Decimal(-20)),
                include_vat=VatInclusion.EXCLUDED,
            ),
        ]
    )

    errors = payment_list.validate()

    assert len(errors) == 2  # noqa: PLR2004


# ---------- TotalAmount ----------


def test_total_amount_is_correct_collects_errors_from_total_and_taxes():
    total = TotalAmount(
        total=Payment(
            amount=Money(value=Decimal(-100), transcription=None),
            vat=Vat(amount=None, rate=None),
            include_vat=VatInclusion.EXCLUDED,
        ),
        taxes=PaymentList(
            [
                Payment(
                    amount=None,
                    vat=Vat(
                        amount=Money(value=Decimal(-20), transcription=None),
                        rate=Decimal(-20),
                    ),
                    include_vat=VatInclusion.INCLUDED,
                )
            ]
        ),
    )

    errors = total.validate()

    assert len(errors) == 3  # noqa: PLR2004


def test_total_amount_get_moneys_returns_total_and_tax_moneys():
    total = make_payment(amount="1000")
    tax1 = make_payment(amount="200")
    tax2 = make_payment(amount="100")

    total_amount = TotalAmount(
        total=total,
        taxes=PaymentList([tax1, tax2]),
    )

    assert total_amount.get_moneys() == [
        total.amount,
        tax1.amount,
        tax2.amount,
    ]
