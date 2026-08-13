from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from apps.experiences.models import ExperienceDraft

from ..models import Payment, Plan

User = get_user_model()


def make_user(email="user@example.com"):
    return User.objects.create_user(
        email=email,
        first_name="Test",
        last_name="User",
        password="strong-pass-123",
    )


def make_draft(owner):
    return ExperienceDraft.objects.create(owner=owner)


def make_payment(*, draft, plan, attempt_number, status=Payment.Status.PENDING, **overrides):
    defaults = {
        "draft": draft,
        "owner": draft.owner,
        "plan": plan,
        "attempt_number": attempt_number,
        "amount": plan.price,
        "currency": plan.currency,
        "status": status,
        "external_reference": f"memoverse:draft:{draft.id}:attempt:{attempt_number}",
        "idempotency_key": f"idem-{draft.id}-{attempt_number}",
    }
    defaults.update(overrides)
    return Payment.objects.create(**defaults)


class PlanSeedTests(TestCase):
    """A migration 0002_seed_initial_plans já deve ter rodado ao montar o banco de teste."""

    def test_seed_creates_both_initial_plans(self):
        codes = set(Plan.objects.values_list("code", flat=True))
        self.assertEqual(codes, {"essential", "stellar"})

    def test_essential_plan_values(self):
        plan = Plan.objects.get(code="essential")
        self.assertEqual(plan.name, "MemoVerse Essencial")
        self.assertEqual(plan.price, Decimal("29.99"))
        self.assertEqual(plan.currency, "BRL")
        self.assertIs(plan.get_feature("stars_enabled"), False)

    def test_stellar_plan_values(self):
        plan = Plan.objects.get(code="stellar")
        self.assertEqual(plan.name, "MemoVerse Estelar")
        self.assertEqual(plan.price, Decimal("39.99"))
        self.assertEqual(plan.currency, "BRL")
        self.assertIs(plan.get_feature("stars_enabled"), True)


class PlanTests(TestCase):
    def test_code_must_be_unique(self):
        Plan.objects.create(code="dup", name="Dup", price=Decimal("1.00"))
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Plan.objects.create(code="dup", name="Dup 2", price=Decimal("2.00"))

    def test_get_feature_returns_stored_value(self):
        plan = Plan.objects.create(
            code="custom", name="Custom", price=Decimal("9.99"), features={"max_photos": 20}
        )
        self.assertEqual(plan.get_feature("max_photos"), 20)

    def test_get_feature_returns_default_when_key_is_missing(self):
        plan = Plan.objects.create(code="custom2", name="Custom 2", price=Decimal("9.99"))
        self.assertIsNone(plan.get_feature("ai_enabled"))
        self.assertIs(plan.get_feature("ai_enabled", default=False), False)


class PaymentConstraintTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.draft = make_draft(self.user)
        self.plan = Plan.objects.get(code="essential")

    def test_draft_and_attempt_number_must_be_unique(self):
        make_payment(draft=self.draft, plan=self.plan, attempt_number=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_payment(draft=self.draft, plan=self.plan, attempt_number=1)

    def test_only_one_active_payment_per_draft(self):
        make_payment(draft=self.draft, plan=self.plan, attempt_number=1, status=Payment.Status.PENDING)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_payment(
                    draft=self.draft, plan=self.plan, attempt_number=2, status=Payment.Status.IN_PROCESS
                )

    def test_multiple_payments_with_null_mp_order_id_are_allowed(self):
        # Duas tentativas terminais (rejeitadas) no mesmo draft, ambas sem mp_order_id:
        # NULL != NULL na constraint única, então as duas linhas devem coexistir.
        make_payment(draft=self.draft, plan=self.plan, attempt_number=1, status=Payment.Status.REJECTED)
        make_payment(draft=self.draft, plan=self.plan, attempt_number=2, status=Payment.Status.REJECTED)
        self.assertEqual(
            Payment.objects.filter(draft=self.draft, mp_order_id__isnull=True).count(), 2
        )


class PaymentAmountFreezeTests(TestCase):
    def test_amount_and_currency_are_frozen_at_creation(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.get(code="stellar")

        payment = make_payment(draft=draft, plan=plan, attempt_number=1)
        self.assertEqual(payment.amount, Decimal("39.99"))
        self.assertEqual(payment.currency, "BRL")

        plan.price = Decimal("49.99")
        plan.save(update_fields=["price"])

        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("39.99"))
        self.assertEqual(Plan.objects.get(pk=plan.pk).price, Decimal("49.99"))


class PaymentPlanProtectTests(TestCase):
    def test_plan_cannot_be_deleted_while_referenced_by_a_payment(self):
        user = make_user()
        draft = make_draft(user)
        plan = Plan.objects.create(code="temp-plan", name="Temp", price=Decimal("9.99"))
        make_payment(draft=draft, plan=plan, attempt_number=1)

        with self.assertRaises(ProtectedError):
            plan.delete()
