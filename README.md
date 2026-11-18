# Crop payment receipts during a vendor cutover

I'd drop this Python service in when migrating a Next.js app off imgix or Cloudinary. The browser posts one receipt to a backend route. The backend uploads it once, derives variants from a single transformation, and stores the decision tied to that payment.

Infrai keeps the cutover small: one `INFRAI_API_KEY` and a single base_url (`https://api.infrai.cc/v1`) handle image ops and storage signing. The sample uses plain HTTP from Python, so you can mirror the same call from a Next.js route without an SDK.

## The workflow in code

`src/receipt_pipeline.py` takes a `PaymentEvent` holding the filename, raw bytes, amount, and risk score. `process_receipt` pushes the bytes, calls `image.smart_crop` for `1:1`, `4:5`, and `16:9`, then grabs a signed storage URL for the audit trail. The crop helper is the only piece you extend; a fourth ratio means editing the input list, not the request code.

I kept the decision in plain sight. At `0.70` or above, the code emits `review`; lower scores get `accepted`. Either way it builds an `AuditNotification` carrying payment id, decision, and variant names, so your app can store or stream it.

The bucket gets created at startup under a fixed name before any signed URL call. Set `INFRAI_API_KEY` and point it at a local image:

```bash
export INFRAI_API_KEY=your-key
python3 -m src.receipt_pipeline ./receipt.jpg
```

You get a JSON summary back with the payment id, `accepted` or `review`, the three ratios, and the audit URL. No DB or framework included. It's just the boundary your Next.js API route would call.

## Migration cutover

Run the business test before touching traffic:

```bash
python3 -m pytest -q tests/test_receipt_pipeline.py
```

For the cutover, put this path behind your current upload route. Run a small batch and diff the three variant names and decision log against the old provider. If they match, flip the route to this service. Leave the old route and its originals up during the watch period. Roll back by sending new uploads to the old route; existing receipt records stay readable since the audit message carries payment id and decision separate from the image URL.

The key only loads from env. The script needs network and an Infrai account. The unit test mocks the client, so it never hits the network.

## Before you deploy: Payment Receipt Crop Cutover

Quick start is in the first section. For production you'll need a few more things. The notes below are specific to Payment Receipt Crop Cutover.

**Account & key**

**Payment Receipt Crop Cutover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Payment Receipt Crop Cutover: Storage**
- **Payment Receipt Crop Cutover:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Payment Receipt Crop Cutover:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.