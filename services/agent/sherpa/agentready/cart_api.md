# PayPal Cart API v1: the contract Sherpa generates

This is the merchant side of PayPal's Cart API v1 (agentic commerce). PayPal's Commerce Platform calls these endpoints on the merchant after Store Sync onboarding. In this hackathon build, Sherpa's buyer agent plays that caller role against the sandbox.

The PayPal docs for Store Sync moved during the build, so field-level details were checked against PayPal's published Cart API schema as implemented in PayPal's official WooCommerce plugin (`woocommerce-paypal-payments`, module `ppcp-store-sync`). See `docs/DECISIONS.md`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/merchant-cart` | Create a cart, validate it and create the PayPal order. Returns `201`. |
| `GET` | `/merchant-cart/{id}` | Read the stored cart. `404 CART_NOT_FOUND` if unknown. |
| `PUT` | `/merchant-cart/{id}` | **Replace** the whole cart (omitted fields are cleared), re-validate and update the PayPal order amount. |
| `POST` | `/merchant-cart/{id}/checkout` | Complete checkout. If the cart is not ready it returns `200` with the cart and its issues; once the buyer has approved the PayPal order it captures it and returns `status: COMPLETED`. |

## Request body (POST and PUT)

```json
{
  "items": [{ "item_id": "vanilla-bean-celebration", "variant_id": null, "quantity": 1 }],
  "customer": { "email_address": "buyer@example.com", "name": { "given_name": "Alex", "surname": "Rivera" } },
  "shipping_address": {
    "address_line_1": "500 Market St", "admin_area_2": "San Francisco", "admin_area_1": "CA",
    "postal_code": "94105", "country_code": "US"
  },
  "checkout_fields": [{ "type": "DELIVERY_DATE_PREFERENCE", "value": "2026-11-07" }],
  "payment_method": { "type": "paypal" }
}
```

Prices sent by the caller are ignored. The store always prices items from its own catalog.

## Cart response

```json
{
  "id": "cart_8f2c1a",
  "status": "CREATED",
  "validation_status": "INVALID",
  "validation_issues": [
    {
      "code": "DATA_ERROR",
      "type": "MISSING_FIELD",
      "message": "A delivery date is required for preorder cakes.",
      "user_message": "Which day should we deliver your cake?",
      "field": "checkout_fields.DELIVERY_DATE_PREFERENCE",
      "context": { "specific_issue": "MISSING_CHECKOUT_FIELDS" },
      "resolution_options": [{ "action": "PROVIDE_MISSING_FIELD" }]
    }
  ],
  "items": [
    {
      "item_id": "vanilla-bean-celebration", "quantity": 1, "name": "Vanilla Bean Celebration Cake",
      "price": { "currency_code": "USD", "value": "78.00" }
    }
  ],
  "totals": {
    "subtotal": { "currency_code": "USD", "value": "78.00" },
    "shipping": { "currency_code": "USD", "value": "0.00" },
    "tax": { "currency_code": "USD", "value": "0.00" },
    "total": { "currency_code": "USD", "value": "78.00" }
  },
  "payment_method": { "type": "paypal", "token": "5O190127TN364715T" }
}
```

- `status`: `CREATED` after create, `INCOMPLETE` while something is missing, `COMPLETED` after a successful checkout.
- `validation_status`: `VALID` only when `validation_issues` is empty.
- `payment_method.token` is the PayPal Orders v2 order id (the `ec_token`). The buyer approves it on PayPal, then the caller posts to `/checkout`.
- After checkout the response adds `payment_confirmation: { "merchant_order_number": "...", "order_review_page": "https://..." }`.
- Issue `code` values: `INVENTORY_ISSUE`, `PRICING_ERROR`, `SHIPPING_ERROR`, `DATA_ERROR`, `BUSINESS_RULE_ERROR`, `PAYMENT_ERROR`. Issue `type` values: `MISSING_FIELD`, `INVALID_DATA`, `BUSINESS_RULE`, `SYSTEM_ERROR`.

## Errors

Errors replace the cart body with `{ "name": "...", "message": "...", "debug_id": "..." }`:

| Name | Status |
|---|---|
| `INVALID_REQUEST` | 400 |
| `CART_NOT_FOUND` | 404 |
| `UNPROCESSABLE_ENTITY` | 422 |
| `INTERNAL_SERVER_ERROR` | 500 |

## Catalog feed

`GET /catalog.json` returns `{ "items": [...] }`, each with `id`, `title`, `description`, `price: { currency_code, value }`, `availability` (`in_stock` / `out_of_stock` / `preorder`), `image_url`, `url` and optional `variants`.
