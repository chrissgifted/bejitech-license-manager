# Bejitech License Manager: Screen Wireframes

Phase 1 deliverable. Low-fidelity layouts; visual styling (colours, icons, spacing) is applied in Phase 2.

## Design language

- **Window:** native macOS title bar, minimum 1200 × 760, remembers size/position.
- **Layout:** fixed left sidebar (220 px) + content area. Each page has a header row (title, search, primary action button) and a body.
- **Style:** light theme first (dark mode follows macOS later), white cards on a soft grey background, one accent colour (Bejitech deep blue `#1F4E9B`), status colours green / amber / red / grey.
- **Typography:** macOS system font (SF Pro) at 13 px body, 20 px page titles; monospace for licence keys.
- **Tables:** sortable columns, instant search box, status pills, double-click opens details, right-click menu.
- **Money:** always shown as `TZS 150,000` (thousands separators, no decimals).
- **Keys:** always masked `XXXXX-XXXXX-XXXXX-XXXXX-7HQ2D` with an eye (reveal) and copy button.

---

## 0. First run and login

```
┌───────────────────────────────────────────────┐
│              [ Bejitech logo ]                │
│          Bejitech License Manager             │
│                                               │
│  First-time setup                             │
│  Administrator name   [______________]        │
│  Username             [______________]        │
│  Password             [______________]        │
│  Confirm password     [______________]        │
│  Recovery passphrase  [______________]  (?)   │
│  ⚠ Write the recovery passphrase down. It is  │
│    the only way to recover licence keys if    │
│    this Mac's Keychain is lost.               │
│                     [ Create account ]        │
└───────────────────────────────────────────────┘
Later launches: Username / Password / [ Sign in ]
```

## 1. Main window and Dashboard

```
┌──────────────┬───────────────────────────────────────────────────────────────┐
│ ◆ BEJITECH   │ Dashboard                                  18 Nov 2026  👤 Admin│
│ License Mgr  ├───────────────────────────────────────────────────────────────┤
│              │ ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐  │
│ ▣ Dashboard  │ │Products  ││Keys      ││Available ││Allocated ││Fully used│  │
│ ▢ Products   │ │   12     ││   86     ││ activ.214││ activ.391││ keys  41 │  │
│ ▢ Inventory  │ └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘  │
│ ▢ New Sale   │ ┌──────────┐┌──────────┐┌──────────────┐┌──────────────┐┌─────┐│
│ ▢ Customers  │ │Customers ││Sales     ││Revenue       ││Purchase costs││Gross││
│ ▢ Sales Hist.│ │  158     ││  402     ││TZS 18,450,000││TZS 6,120,000 ││profit│
│ ▢ Deliv.Notes│ └──────────┘└──────────┘└──────────────┘└──────────────┘└─────┘│
│ ▢ Reports    │  Period: [This month ▾]                                        │
│ ▢ Backup     │ ┌─ Low-stock alerts ───────────────┐┌─ Revenue (last 6 mo.) ─┐ │
│ ▢ Settings   │ │ ⚠ Windows 11 Pro       2 left    ││  ▂ ▃ ▅ ▄ ▆ █            │ │
│              │ │ ⚠ Office 2021 Pro Plus 1 left    ││                         │ │
│              │ │   [ Add keys ]                   │└─────────────────────────┘ │
│              │ └──────────────────────────────────┘                           │
│              │ ┌─ Recent sales ─────────────────────────────────────────────┐ │
│ ──────────── │ │ SAL-2026-00402  Amina H.   Office 2024 PP ×1  TZS 85,000   │ │
│ Last backup: │ │ SAL-2026-00401  Kilimo Ltd Windows 11 Pro ×5  TZS 300,000  │ │
│ today 09:12 ✓│ └────────────────────────────────────────────────────────────┘ │
│ [ Lock 🔒 ]  │                                     [ + New Sale ]             │
└──────────────┴───────────────────────────────────────────────────────────────┘
```

## 2. Software Products

```
Software Products                    [🔍 Search products…]  [Publisher ▾] [Category ▾]
                                     [☐ Show archived]              [ + Add Product ]
┌──────┬─────────────────────────────────┬───────────┬───────┬──────────┬──────────┬───────┐
│ Logo │ Product                         │ Publisher │ Type  │ Price    │ Available│ Status│
├──────┼─────────────────────────────────┼───────────┼───────┼──────────┼──────────┼───────┤
│ [▣]  │ Office 2024 Professional Plus   │ Microsoft │ Retail│ 85,000   │   34     │ ●Active│
│ [▣]  │ Office 2021 Professional Plus   │ Microsoft │ Retail│ 65,000   │    1 ⚠   │ ●Active│
│ [▣]  │ Office 2019 Professional Plus   │ Microsoft │ Retail│ 45,000   │   12     │ ●Active│
│ [▣]  │ Windows 11 Pro                  │ Microsoft │ Retail│ 60,000   │    2 ⚠   │ ●Active│
└──────┴─────────────────────────────────┴───────────┴───────┴──────────┴──────────┴───────┘
```

**Add / Edit Product dialog (tabs)**

```
┌ Add Product ────────────────────────────────────────────────────────────┐
│ [General] [Pricing] [Download & Instructions] [Logo]                    │
│                                                                         │
│ General                                                                 │
│  Publisher     [Microsoft        ▾] [+]   Category [Office Suites ▾] [+]│
│  Product line  [Microsoft Office ▾] [+]                                 │
│  Version       [2024      ]   Edition [Professional Plus      ]         │
│  Platform      [Windows ▾]    Licence type [Retail ▾]                   │
│  Display name  [Microsoft Office 2024 Professional Plus] (auto-filled)  │
│  Low-stock alert when available activations below [ 3 ]                 │
│                                                                         │
│ Download & Instructions                                                 │
│  Download URL   [https://…                              ] ☐ Verified    │
│  Link label     [Download Microsoft Office 2024         ]               │
│                 (left blank → "Download <product name>")                │
│  Installation instructions  [multi-line text…                     ]     │
│  Activation instructions    [multi-line text…                     ]     │
│                                                                         │
│ Logo:  [ preview 120×120 ]  [ Choose image… ]  PNG/JPG/SVG, ≤ 2 MB      │
│                                          [ Cancel ]  [ Save Product ]   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. License Inventory

```
License Inventory      [🔍 Search ref, product, supplier, last 5 chars…]
Filter: (All) (Available) (Partial) (Fully allocated) (Expired) (Disabled)
Product [All ▾]   Supplier [All ▾]                              [ + Add License ]
┌───────────────┬──────────────────────┬─────────────────────────────┬────┬────┬────┬──────────┐
│ Ref           │ Product              │ Key                         │Cap.│Used│Left│ State    │
├───────────────┼──────────────────────┼─────────────────────────────┼────┼────┼────┼──────────┤
│INV-2026-00031 │ Office 2024 PP       │ XXXXX-…-7HQ2D   👁 ⧉        │ 5  │ 3  │ 2  │◐ Partial │
│INV-2026-00030 │ Windows 11 Pro       │ XXXXX-…-K9TQW   👁 ⧉        │ 1  │ 1  │ 0  │● Full    │
│INV-2026-00012 │ Office 2019 PP       │ XXXXX-…-PP2M4   👁 ⧉        │ 1  │ 0  │ 1  │○ Available│
│INV-2025-00090 │ Office 2021 PP       │ XXXXX-…-3JRT8   👁 ⧉        │ 1  │ 0  │ 1  │✕ Expired │
└───────────────┴──────────────────────┴─────────────────────────────┴────┴────┴────┴──────────┘
┌ Detail: INV-2026-00031 ────────────────────────────────────────────────────┐
│ Supplier: KeySupply Ltd  · Bought 01 Nov 2026 · USD 12.00 @ 2,650 = TZS 31,800│
│ Multi-customer: Yes · Reassignable: No · Expires: — · Restrictions: Windows only│
│ Allocation history                                                          │
│  18 Nov 14:02  ALLOCATED  2 → Kilimo Ltd     SAL-2026-00401   0 → 2         │
│  18 Nov 16:40  CONFIRMED  2   Kilimo Ltd                                    │
│  19 Nov 10:05  ALLOCATED  1 → Amina H.       SAL-2026-00402   2 → 3         │
│                           [ Edit ] [ Disable ] [ Adjust capacity… ]         │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Add License dialog:** product, licence key (masked input, paste supported, duplicate check on save), supplier, purchase date, cost + currency (USD shows exchange-rate field and the TZS result), permitted capacity, multi-customer / reassignable (defaults from licence type), expiry date (optional), restrictions, notes. Option: "Add several keys at once" (one per line) for bulk entry.

## 4. New Sale (smart allocation)

```
New Sale                                                     SAL-2026-00403 (next)
┌ 1 Customer ────────────────────────────────────────────────────────────────┐
│ [🔍 Type name, phone or email…             ▾]   [ + New customer ]         │
│ ✓ Kilimo Ltd · Joseph M. · +255 7xx xxx xxx · 4 previous purchases         │
└────────────────────────────────────────────────────────────────────────────┘
┌ 2 Product & quantity ──────────────────────────────────────────────────────┐
│ Product [Microsoft Office 2024 Professional Plus ▾]  Quantity [ 2 ]        │
│ In stock: 34 activations across 9 keys                                     │
└────────────────────────────────────────────────────────────────────────────┘
┌ 3 Recommended licence ─────────────────────────────────────────────────────┐
│ ★ INV-2026-00031  XXXXX-…-7HQ2D  2 of 5 left  covers full quantity         │
│   Why: partially used key, fills it before opening a new one               │
│   Other options:                                                           │
│   ○ INV-2026-00033  …-M2KQ1  5 of 5 left                                   │
│   ○ Split across keys (advanced)                                           │
└────────────────────────────────────────────────────────────────────────────┘
┌ 4 Price & payment ─────────────────────────────────────────────────────────┐
│ Unit price TZS [85,000]  × 2 = 170,000   Discount TZS [10,000]             │
│ Total  TZS 160,000                                                         │
│ Payment [Mobile money ▾]  Reference [M-Pesa QK7…]   Date [18/11/2026]      │
└────────────────────────────────────────────────────────────────────────────┘
After sale: INV-2026-00031 will have 0 of 5 left (fully allocated)
                         [ Cancel ]   [ Complete sale & create delivery note ]
```

On success: confirmation panel with **Preview delivery note · Save PDF · Print · Prepare email · New sale**.

## 5. Customers

```
Customers   [🔍 Search name, organisation, phone, email…]          [ + Add Customer ]
┌───────────┬──────────────────┬──────────────┬────────────────┬──────────┬───────────┐
│ Ref       │ Name             │ Organisation │ Phone          │ Purchases│ Total spent│
├───────────┼──────────────────┼──────────────┼────────────────┼──────────┼───────────┤
│ CUS-00158 │ Joseph M.        │ Kilimo Ltd   │ +255 7xx…      │    5     │ 1,240,000 │
└───────────┴──────────────────┴──────────────┴────────────────┴──────────┴───────────┘
Customer detail (right pane): contact info · purchase history (sale ref, date,
product, qty, key last-5, delivery note link) · [ Edit ] [ New sale for customer ]
```

## 6. Sales History

```
Sales History  [🔍 Ref, customer, product…]  From [01/11/2026] To [18/11/2026]
Status [All ▾]  Payment [All ▾]                                   [ Export CSV ]
┌───────────────┬───────────┬───────────┬────────────────┬───┬──────────┬──────────┬────────┐
│ Ref           │ Date      │ Customer  │ Product        │Qty│ Total    │ Payment  │ Status │
├───────────────┼───────────┼───────────┼────────────────┼───┼──────────┼──────────┼────────┤
│SAL-2026-00402 │18 Nov 2026│ Amina H.  │ Office 2024 PP │ 1 │  85,000  │ Cash     │●Done   │
│SAL-2026-00399 │15 Nov 2026│ Baraka S. │ Windows 11 Pro │ 1 │  60,000  │ Bank     │✕Cancel.│
└───────────────┴───────────┴───────────┴────────────────┴───┴──────────┴──────────┴────────┘
Detail: line items, allocations (key last-5, ALLOCATED/CONFIRMED), delivery note,
[ Mark activation confirmed ] [ Cancel sale… ] [ Open delivery note ]
```

**Cancel sale dialog:** reason (required) · for each allocation: "Return 2 activations to INV-2026-00031" (only offered if not confirmed and key is reassignable; otherwise shows "Will be recorded as consumed: confirmed / not reassignable") · type `CANCEL` to confirm.

## 7. Delivery Notes

```
Delivery Notes  [🔍 DN number, customer, sale ref…]
┌───────────────┬───────────┬───────────────┬────────────┬─────────┐
│ Number        │ Date      │ Sale          │ Customer   │ Status  │
├───────────────┼───────────┼───────────────┼────────────┼─────────┤
│DN-2026-00402  │18 Nov 2026│SAL-2026-00402 │ Amina H.   │●Issued  │
└───────────────┴───────────┴───────────────┴────────────┴─────────┘
┌ Preview ──────────────────────────────┐  [ Save PDF… ] [ Print… ]
│  (rendered page 1 of PDF)             │  [ Prepare email ] [ Regenerate ]
│                                       │  [ Show in Finder ]
└───────────────────────────────────────┘
```

**PDF delivery note layout (A4)**

```
┌──────────────────────────────────────────────────────────────┐
│ ▬▬▬▬▬▬▬▬▬▬▬ accent band (colour adapts to product) ▬▬▬▬▬▬▬▬▬▬ │
│ [Product logo]                         DELIVERY NOTE          │
│                                        No. DN-2026-00402      │
│                                        Date 18 November 2026  │
│ FROM                          TO                              │
│ Christian Joel Mtei           Amina H.                        │
│ Bejitech                      Organisation                    │
│ Phone · Email (Settings)      Phone · Email                   │
│──────────────────────────────────────────────────────────────│
│ SOFTWARE                                                      │
│ Microsoft Office 2024 Professional Plus · Windows · Retail    │
│ Activations purchased: 1        Sale ref: SAL-2026-00402      │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ LICENCE KEY   ABCDE-FGHIJ-KLMNO-PQRST-7HQ2D (monospace)  │ │
│ └──────────────────────────────────────────────────────────┘ │
│ DOWNLOAD   ▶ Download Microsoft Office 2024   (clickable)     │
│ INSTALLATION       1. … 2. … 3. …                             │
│ ACTIVATION         1. … 2. …                                  │
│──────────────────────────────────────────────────────────────│
│ Received by: ____________   Signature: ________  Date: ____   │
│ Thank you for your purchase · Keep this document safe         │
└──────────────────────────────────────────────────────────────┘
```

## 8. Reports

```
Reports
[Inventory] [Sales] [Customers] [Activation balances] [Profit]
Period [This month ▾]  Product [All ▾]                [ Export PDF ] [ Export CSV ]
┌ Profit, November 2026 ──────────────────────────────────────────┐
│ Product          Units  Revenue      Cost        Gross profit  Margin │
│ Office 2024 PP     22   1,870,000    699,600     1,170,400     62.6% │
│ …                                                                     │
│ TOTAL                   …                                             │
└─────────────────────────────────────────────────────────────────┘
```

## 9. Backup & Restore

```
Backup & Restore
┌ Create backup ──────────────────────────────────────────────┐
│ Destination [~/Library/…/backups ▾] [Choose…]               │
│ Backup password [________]  Confirm [________]              │
│                          [ Create encrypted backup ]        │
│ Automatic backup: [Daily ▾] keep last [10] (uses saved pwd) │
└─────────────────────────────────────────────────────────────┘
┌ Backup history ─────────────────────────────────────────────┐
│ 18 Nov 2026 09:12  Manual  4.2 MB  ✓ Verified  [Verify again]│
└─────────────────────────────────────────────────────────────┘
┌ Restore ────────────────────────────────────────────────────┐
│ [ Choose backup file… ]  password [______]                  │
│ ⚠ Replaces all current data. A safety backup is made first. │
│ Type RESTORE to confirm [_______]          [ Restore ]      │
└─────────────────────────────────────────────────────────────┘
```

## 10. Settings

```
Settings
[Business] [Sales & currency] [Licence types] [Security] [Delivery notes] [About]

Business:        Seller name [Christian Joel Mtei]  Business name [Bejitech]
                 Phone [__________]  Email [__________]  Address [__________]
Sales & currency: Default currency TZS · USD→TZS rate [2,650.00] (history ▸)
                 Reference prefixes INV / SAL / DN / CUS · Default low-stock level [3]
Licence types:   table of types with Multi-customer ☐ / Reassignable ☐ toggles
Security:        Change password · Change recovery passphrase · Auto-lock after [15 min]
                 Clipboard clear after [60 s] · View audit log
Delivery notes:  Show signature section ☑ · Footer text · Accent colour
About:           Version, data folder [Show in Finder], licences of open-source libraries
```
