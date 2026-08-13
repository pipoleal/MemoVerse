from django.test import TestCase

from ..models import Payment
from ..services.status_mapping import map_order_status


class MapOrderStatusTests(TestCase):
    def test_created_maps_to_pending(self):
        self.assertEqual(map_order_status("created"), Payment.Status.PENDING)

    def test_processing_maps_to_in_process(self):
        self.assertEqual(map_order_status("processing"), Payment.Status.IN_PROCESS)

    def test_action_required_maps_to_action_required(self):
        self.assertEqual(map_order_status("action_required"), Payment.Status.ACTION_REQUIRED)

    def test_processed_maps_to_approved(self):
        self.assertEqual(map_order_status("processed"), Payment.Status.APPROVED)

    def test_canceled_maps_to_cancelled(self):
        self.assertEqual(map_order_status("canceled"), Payment.Status.CANCELLED)

    def test_expired_maps_to_expired(self):
        self.assertEqual(map_order_status("expired"), Payment.Status.EXPIRED)

    def test_failed_maps_to_rejected(self):
        # "failed" não existe em Payment.Status; documentado como o estado
        # terminal desfavorável mais próximo.
        self.assertEqual(map_order_status("failed"), Payment.Status.REJECTED)

    def test_refunded_maps_to_refunded(self):
        self.assertEqual(map_order_status("refunded"), Payment.Status.REFUNDED)

    def test_charged_back_is_not_mapped(self):
        # De propósito: contestação pós-aprovação é fora de escopo desta
        # fase — o chamador decide o que fazer com None (nunca inventamos
        # um Payment.Status novo).
        self.assertIsNone(map_order_status("charged_back"))

    def test_unknown_status_is_not_mapped(self):
        self.assertIsNone(map_order_status("something_mp_might_add_later"))

    def test_none_status_is_not_mapped(self):
        self.assertIsNone(map_order_status(None))
