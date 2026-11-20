# Running the web version

## Option A: on your Mac first (free, no accounts needed)

The app runs on your Mac and you open it in a browser: on the Mac itself, and on your phone or tablet
when they're on the same Wi-Fi. When the Mac is off or asleep, the app is off too.

1. Install Python 3.12 or newer from <https://www.python.org/downloads/> (skip if you already did for the
   desktop app).
2. Go to <https://github.com/chrissgifted/bejitech-license-manager>, click the green **Code** button and choose
   **Download ZIP**. Double-click the ZIP in Downloads to unpack it.
3. Open the unpacked folder and double-click **Start Bejitech Web.command**.
   If macOS says it can't be opened: right-click it → **Open** → **Open**.
   If macOS asks whether Python may accept incoming connections, click **Allow** (needed for your phone).
4. A Terminal window opens. The first time it takes a minute or two, then shows:
   - the address for this Mac: **http://localhost:8000**
   - the address for your phone, like **http://192.168.1.23:8000**
   - the **setup code** you need once.
5. Open http://localhost:8000 in Safari or Chrome. Create the administrator (setup code, name, username,
   password, recovery passphrase) and turn on two-step login with Google or Microsoft Authenticator.
6. Leave the Terminal window open while you use the app. To stop it, press **Ctrl + C** in that window.
   To start again later, double-click **Start Bejitech Web.command** again.

Your web data and secret keys are kept in the **BejitechWeb** folder in your home folder (separate from
the desktop app's data). Keep a copy of the file **BejitechWeb/web.env** somewhere safe: it holds the key
that unlocks your licence keys. Only use the phone address on your own Wi-Fi at home or the office, not on
public Wi-Fi.

Terminal alternative to step 3: `cd ~/Downloads/bejitech-license-manager-main && bash scripts/run_web_local.sh`

---

# Option B: putting the web version online (Render + Namecheap)

This guide takes about 30 minutes. You do steps 1, 2, 4 and 5 (they need your own accounts and card);
I do step 3 (putting the code on GitHub). At the end the app opens at **https://app.bejitech.com** on any
phone, tablet or computer.

What it costs: roughly **US $14–15 a month** on Render (web server about $7, database about $7, 1 GB file
disk about $0.25). Your bejitech.com domain is already paid for. Render shows the exact price before you confirm.

---

## Step 1. Create a GitHub account and an empty private repository (5 minutes)

Render installs the app from GitHub, a site that stores code.

1. Go to <https://github.com> and sign in (you already have the account **chrissgifted**).
2. Click **+** (top right) → **New repository**.
3. Repository name: `bejitech-license-manager`
4. Choose **Private**. Leave every other box unticked.
5. Click **Create repository**.
6. Tell me in the project thread that it is created. I will put the code in it (step 3).
   If I ask you to, open <https://claude.ai/connect-github> once so I can reach it.

## Step 2. Create the Render account (5 minutes)

1. Go to <https://render.com> → **Get Started** → **Sign up with GitHub** (use the same GitHub account).
2. When Render asks, allow it to see the repository `bejitech-license-manager` only.
3. Add a payment card: **Account settings → Billing → Add card**.
   A Visa or Mastercard debit card from a Tanzanian bank works. If your bank card is refused for online
   payments, a virtual Visa card from M-Pesa (Vodacom) or Airtel Money works too.

## Step 3. I put the code on GitHub

I push the app to your repository, including a file (`render.yaml`) that tells Render exactly what to create.
I'll tell you when it's done.

## Step 4. Create the app on Render (10 minutes)

1. In Render click **New +** → **Blueprint**.
2. Choose the repository `bejitech-license-manager` → **Connect**.
3. Render lists what it will create: **bejitech-app** (web service), **bejitech-db** (database) and a
   1 GB disk, all in **Frankfurt**. Click **Apply** / **Deploy Blueprint**.
4. Wait until bejitech-app shows **Live** (5–10 minutes the first time).
5. Open **bejitech-app → Environment** and copy two values into a safe place (a password manager, or
   written on paper and kept safe):
   - **BEJITECH_DEK**: the key that encrypts your licence keys. **Never share it and never lose it.**
     Without it (or your recovery passphrase) the licence keys can't be read.
   - **BEJITECH_SETUP_TOKEN**: you type it once in the next step.
6. Click the address Render shows at the top (it looks like `https://bejitech-app.onrender.com`).
7. The **Create the administrator** page opens. Enter the setup code (BEJITECH_SETUP_TOKEN), your name,
   a username, a password and a recovery passphrase. Write the recovery passphrase down.
8. Turn on two-step login: install **Google Authenticator** or **Microsoft Authenticator** on your phone,
   tap **+**, scan the square code on the screen, and type the 6-digit code the app shows.

From now on you sign in with your password **and** the 6-digit code from your phone.

## Step 5. Use your own address: app.bejitech.com (5 minutes + waiting)

Your main bejitech.com website and email are not touched; this only adds "app." in front.

**In Render**

1. Open **bejitech-app → Settings → Custom Domains → Add Custom Domain**.
2. Type `app.bejitech.com` → **Save**. Render shows a value to point to, like `bejitech-app.onrender.com`.

**In Namecheap**

1. Sign in at <https://www.namecheap.com> → **Domain List** → next to bejitech.com click **Manage**.
2. Open the **Advanced DNS** tab.
3. Under **Host Records** click **Add New Record** and fill in:

   | Type | Host | Value | TTL |
   |---|---|---|---|
   | CNAME Record | `app` | the value Render showed (e.g. `bejitech-app.onrender.com`) | Automatic |

4. Click the green tick to save.

**Back in Render**, click **Verify** next to app.bejitech.com. It usually works within 30 minutes (sometimes
a few hours). Render then sets up the padlock (HTTPS) by itself.

Open **https://app.bejitech.com** on your phone. To put it on the home screen like an app:
iPhone: Share → **Add to Home Screen**. Android (Chrome): ⋮ → **Add to Home screen**.

---

## Good to know

- **Backups**: Render backs up the database every day automatically (kept 7 days on this plan).
- **Updates**: when I improve the app I push to GitHub and Render updates it by itself in a few minutes.
- **Lost phone**: sign-in needs the 6-digit code. If you lose your phone, open **bejitech-app → Shell** in
  Render and run `python -m bejitech.web reset-two-step admin` (use your username). At your next sign-in
  you scan a new code with your new phone. Only someone signed in to your Render account can do this.
- **Your Mac data**: moving your existing products, keys, customers and sales into the web version is
  Phase 3. Until then keep using the Mac app for real work.
