# Sector & Position Design — fund-watch

Date: 2026-03-03

## Goal

Add fund sector (板块), position amount (持仓金额), and position percentage (持仓占比) to each fund. Sector auto-fetched from data source. Position importable via OCR from Alipay/Ant Fortune screenshots or manual input.

## Database Changes

`funds` table adds 3 columns:
- `sector TEXT` — fund sector/category (e.g. "白酒", "医药"), auto-fetched
- `amount REAL` — position amount in CNY, from OCR or manual
- `percentage REAL` — position %, calculated from total

## Backend Changes

1. **fund_source.py**: Add `fetch_fund_info(code)` to get sector from `fund.eastmoney.com/pingzhongdata/{code}.js`
2. **db.py**: ALTER TABLE to add columns (migration-safe)
3. **ocr_service.py**: Enhance to extract amounts (¥1,234.56 patterns) and associate with nearest fund code
4. **main.py**: Update endpoints to accept/return new fields

## API Changes

- `POST /api/funds/{code}` — optional body `{amount?: number}`
- `POST /api/funds/batch` — optional `{amounts?: {code: amount}}`
- `GET /api/funds/overview` — returns sector, amount, percentage
- `POST /api/ocr/fund-code` — returns `matched_funds: [{code, amount?}]`

## Frontend Changes

- Table: add Sector, Amount, Percentage columns
- OCR results: show detected amounts
- Manual add: optional amount input
- Amount inline-editable
- Percentage auto-calculated from totals
