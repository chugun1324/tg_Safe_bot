# Payment Escrow Module (MVP)

This folder contains the first-stage payment scaffold for wallet-based escrow.

## Mode

- `PAYMENTS_MODE=mock` - local testing without real blockchain checks.
- `PAYMENTS_MODE=ton` - planned mode for TON/USDT wallet verification.

## Environment Variables

Required for MVP scaffold:

- `ESCROW_WALLET_ADDRESS` - wallet address where customer sends funds.
- `FIAT_BASE_CURRENCY` - default fiat currency (for example `RUB`).
- `MANUAL_USDT_RATE_RUB` - fixed RUB/USDT rate.
- `MANUAL_USDT_RATE_USD` - fixed USD/USDT rate.
- `PAYMENT_INVOICE_TTL_MINUTES` - invoice lifetime.
- `PAYMENT_TOLERANCE_BPS` - tolerance in basis points (50 = 0.5%).
- `PAYMENT_PROVIDER_NAME` - provider label for audit trail.
- `PAYMENTS_MODE` - `mock` or `ton`.
- `MOCK_WALLET_BALANCE_USDT` - wallet balance emulation in mock mode.
- `PAYMENT_RATE_SOURCE` - rate provider (`manual` for MVP).

Future integration fields:

- `PAYMENT_API_KEY`
- `PAYMENT_API_SECRET`
- `TON_API_URL`
- `TON_API_KEY`
- `TON_USDT_JETTON_MASTER`
