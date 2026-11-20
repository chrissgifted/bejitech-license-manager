# User manual

## Everyday flow
1. **Software Products**: check prices, download links and instructions for what you sell.
2. **License Inventory → Add licence keys**: enter each purchased key (or paste several, one per line).
3. **New Sale**: choose the customer, product and number of activations. The app recommends a key,
   shows how many activations are left, and creates the sale and delivery note in one step.
4. **Delivery Notes**: preview, save, print or prepare an email for the customer.

## Screens

**Dashboard.** Totals for products, keys, available/allocated activations, fully allocated keys, customers,
sales, revenue, purchase costs and gross profit, plus low-stock alerts and recent sales. Choose the sales period
at the top right. *Gross profit* = revenue − cost of the activations sold (each key's cost ÷ its activations).

**Software Products.** Add, edit, search, filter and archive products. Each product has publisher, category,
product, version, edition, platform, licence type, prices, logo (PNG/JPG), download link and friendly link text,
installation and activation instructions, and a low-stock level. If the link text is empty the delivery note shows
"Download <product name>". Tick "verified" only after checking that the link is an authorised download.

**License Inventory.** Every key is encrypted and shown masked (only the last 5 characters). Filter by state:
Available, Partially allocated, Fully allocated, Expired, Disabled. Select a key to see its full allocation
history. Buttons: Reveal (shows the key for 30 seconds), Copy key (clipboard is cleared automatically), Edit,
Adjust capacity (never below what is allocated), Disable/Enable. Viewing or copying a key may ask for your password
again and is always written to the audit log. The app refuses a key that is already in inventory.

**Fixing a wrong product or licence type.** Select the key → *Edit* and change *Product* or *Licence type*.
This is possible until any activation of the key has been sold. After that both fields are locked so past
sales and delivery notes stay correct: cancel those sales with the activations returned to stock, or disable the
key and add it again.

*Multi-customer* and *Reassignable* settings come from the licence type (Settings → Licence types) and can be
changed per key. Turn them on only if the licence terms allow it.

**New Sale.** Smart allocation recommends keys in this order: expiring soonest, then keys already partly used,
then oldest purchase. If no single key has enough activations it splits the quantity across keys. Keys that are
disabled, expired, used up, or belong to another customer (when sharing is not allowed) are never offered.
Saving is all-or-nothing: if anything fails, nothing changes.

**Customers.** Contact details, search, archive and full purchase history.

**Sales History.** Filter by date, status and payment method. Select a sale to see which keys were allocated.
*Mark activation confirmed* records that the customer activated successfully. *Cancel sale* asks for a reason and
shows, for each key, whether its activations can be returned to stock. They are returned only when the activation
was not confirmed **and** either the licence allows reassignment or you tick "The licence key was never given to
the customer". Everything else is recorded as consumed. The delivery note is marked VOID.

**Delivery Notes.** Preview, *Save PDF*, *Print*, *Prepare email* (opens your email app with the message filled in
and shows the PDF in Finder; you attach it by dragging, since email links cannot attach files), *Show in Finder*,
and *Re-issue with current details* (new revision, old one marked VOID).

**Reports.** Inventory, Sales, Customers, Activation balances and Profit, exported as PDF or CSV.

**Backup & Restore.** Create an encrypted backup with a password (verified automatically), verify any backup,
or restore one. Restoring first saves a safety backup of the current data, then closes the app. *Check inventory
consistency* recomputes every key's counters from its history.

**Settings.** Business details for delivery notes, USD→TZS rate, default low-stock level, licence type rules,
delivery note options, auto-lock time, clipboard clearing, password and recovery passphrase, audit log, and the data
folder location.

## Security tips
- Make a backup after each day of sales and keep a copy off the Mac (external disk or iCloud Drive).
- Keep your recovery passphrase and backup password somewhere safe. Without them encrypted data cannot be recovered.
- Use **Lock** (bottom left) when you step away. The app also locks itself after the configured idle time.
