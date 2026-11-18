from src.receipt_pipeline import PaymentEvent, process_receipt


class FakeClient:
    def __init__(self):
        self.calls = []

    def ensure_bucket(self, name):
        self.calls.append(("bucket", name))

    def upload(self, image, filename):
        self.calls.append(("upload", filename))
        return {"ok": True, "data": {"id": "img_123"}}

    def smart_crop(self, image, aspect):
        self.calls.append(("crop", image, aspect))
        return {"ok": True, "data": {"id": f"crop_{aspect}"}}

    def presign_get(self, bucket, key):
        self.calls.append(("presign", bucket, key))
        return {"ok": True, "data": {"url": "https://signed.example/audit"}}


def test_high_risk_payment_is_reviewed_after_all_variants_are_requested():
    client = FakeClient()
    event = PaymentEvent("pay_42", "receipt.jpg", b"jpeg", 4200, 0.70)

    result = process_receipt(event, client)

    assert result.decision == "review"
    assert result.variants == ("pay_42-1x1", "pay_42-4x5", "pay_42-16x9")
    assert [call[2] for call in client.calls if call[0] == "crop"] == ["1:1", "4:5", "16:9"]
    assert client.calls[-1] == ("presign", "payment-receipts", "audit/pay_42.json")
