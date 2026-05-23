# RetailOps CLI — User Guide

A step-by-step guide for daily users. No technical background required.

---

## Table of Contents

1. [Before You Begin](#1-before-you-begin)
2. [Opening a Terminal](#2-opening-a-terminal)
3. [Installation](#3-installation)
   - [Windows](#31-windows)
   - [macOS](#32-macos)
   - [Linux](#33-linux)
   - [Optional: enable tab completion](#optional-enable-tab-completion)
   - [Manual installation for developers](#manual-installation-for-developers)
4. [First-Time Setup — Logging In](#4-first-time-setup--logging-in)
5. [Understanding the Basics](#5-understanding-the-basics)
   - [Previewing a command before it runs (`--dry-run`)](#previewing-a-command-before-it-runs---dry-run)
   - [Output formats](#output-formats)
6. [Typical Daily Workflow](#6-typical-daily-workflow)
   - [Checking Inventory](#61-checking-inventory)
   - [Managing Orders](#62-managing-orders)
   - [Recording a Stock Adjustment](#63-recording-a-stock-adjustment)
   - [Looking Up a Customer](#64-looking-up-a-customer)
7. [Common Tasks](#7-common-tasks)
   - Adding / updating / deleting customers
   - [Viewing or changing system currency settings](#viewing-or-changing-system-currency-settings-manager-access-required)
   - [Checking your configuration](#checking-your-configuration)
   - [Previewing a command before running it](#previewing-a-command-before-running-it)
   - [Resetting a forgotten password](#resetting-a-forgotten-password)
   - [Switching between connections](#switching-between-connections)
   - [Issuing a refund](#issuing-a-refund-administrator-access-required)
   - [Saving output to a file](#saving-output-to-a-file)
8. [Troubleshooting](#8-troubleshooting)
9. [Logging Out](#9-logging-out)
10. [Appendix A — Glossary](#appendix-a--glossary)
11. [Appendix B — Quick Reference Card](#appendix-b--quick-reference-card)

---

## 1. Before You Begin

This guide walks you through installing and using **RetailOps CLI** (`retailops-cli`) — a standalone command-line client that lets you manage RetailOps customers, catalog, inventory, orders, payments, settings, kiosk helpers, and schema tools from your terminal.

**What you will need:**

- A computer running Windows, macOS, or Linux
- An internet connection (or access to your company's internal network, depending on your setup)
- The RetailOps server address — your IT administrator or manager can provide this (it looks something like `http://retailops.yourcompany.com/api/v1`)
- Your RetailOps username (email address) and password

**How to use this guide:**

Find your operating system in [Section 3 — Installation](#3-installation) and follow only the steps for your system. Each operating system has its own set of instructions. After installation, the rest of the guide applies to everyone.

> **Note — Access levels:** Some tasks in this guide require Manager or Administrator access. If you try a command and see a "Permission denied" message, contact your administrator. They can check and update your access level.

---

## 2. Opening a Terminal

A **terminal** (also called a command prompt or command line) is a text-based window where you type instructions for your computer. It might look unfamiliar, but you only need to know a few things to use it:

- Type a command and press **Enter** to run it.
- Commands are case-sensitive — type `retailops-cli` exactly as shown.
- If you make a typo, press **Backspace** to correct it before pressing Enter.
- To copy text in a terminal, select it with your mouse. To paste, use the keyboard shortcut for your system (see below).

### Windows

1. Click the **Start** button (Windows logo in the taskbar).
2. Type **PowerShell** in the search bar.
3. Click **Windows PowerShell** in the results.

A dark blue window will open with a blinking cursor. That means it is ready.

> **Tip:** To paste text into PowerShell, right-click anywhere in the window. To copy, select text with your mouse — it copies automatically.

### macOS

1. Press **Command (⌘) + Space** to open Spotlight Search.
2. Type **Terminal** and press **Enter**.

A white or black window will open with a blinking cursor. That means it is ready.

> **Tip:** To copy in Terminal, press **Command + C**. To paste, press **Command + V**.

### Linux

The method depends on your Linux distribution. Common ways to open a terminal:

- **Ubuntu / GNOME:** Press **Ctrl + Alt + T**, or right-click the desktop and select "Open Terminal".
- **Fedora / KDE:** Press **Ctrl + Alt + T**, or search for "Konsole" in the application menu.
- **Other distributions:** Look for an application called "Terminal", "Konsole", "xterm", or "GNOME Terminal" in your application menu.

A window with a blinking cursor will open. That means it is ready.

> **Tip:** To copy in most Linux terminals, select text with your mouse. To paste, press **Ctrl + Shift + V**.

---

## 3. Installation

RetailOps CLI is installed from GitHub with `pipx`, which keeps it isolated from other Python tools on your computer. The installer checks for Python 3.11 or newer, installs `pipx` if needed, and then installs or updates `retailops-cli`.

RetailOps CLI is only the command-line tool. It does not install the RetailOps backend, RetailOps Kiosk, a database, or server infrastructure. Your administrator still needs to provide the RetailOps API address.

### 3.1 Windows

Open PowerShell and run:

```powershell
irm https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.ps1 | iex
```

When it finishes, verify the installation:

```powershell
retailops-cli --help
```

If PowerShell says `retailops-cli` is not recognized, close PowerShell, open it again, and try the same help command once more.

### 3.2 macOS

Open Terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.sh | bash
```

When it finishes, verify the installation:

```bash
retailops-cli --help
```

If Terminal says `retailops-cli: command not found`, close Terminal, open it again, and try the same help command once more.

### 3.3 Linux

Open a terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/jp72924/retailops-cli/main/install.sh | bash
```

When it finishes, verify the installation:

```bash
retailops-cli --help
```

If your system says `retailops-cli: command not found`, close the terminal, open it again, and try the help command once more.

### Optional: enable tab completion

After installation, you can enable command autocomplete:

```bash
retailops-cli --install-completion
```

The command detects your shell automatically. Close and reopen the terminal once for completion to take effect.

### Manual installation for developers

Use this route only if you are developing the CLI itself or want full control over the environment:

```bash
git clone https://github.com/jp72924/retailops-cli.git
cd retailops-cli
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install and test:

```bash
python -m pip install -e ".[dev]"
python -m pytest tests
retailops-cli --help
```

---

## 4. First-Time Setup — Logging In

Before you can use `retailops-cli`, you need to log in to your RetailOps server. You will only need to do this once — your login is saved automatically, so future sessions start immediately without re-entering your credentials.

**What you need:**

- Your RetailOps server address (provided by your IT administrator — for example: `http://retailops.yourcompany.com/api/v1`)
- Your email address
- Your password

**Run the login command:**

```
retailops-cli auth login --url YOUR_SERVER_ADDRESS
```

Replace `YOUR_SERVER_ADDRESS` with the actual address your IT administrator gave you. For example:

```
retailops-cli auth login --url http://retailops.yourcompany.com/api/v1
```

You will be prompted to enter your email and password:

```
Email: you@yourcompany.com
Password:
```

Type your email, press Enter. Type your password (the characters will not appear on screen — this is normal and means your password is hidden), then press Enter.

If your credentials are correct, you will see:

```
✓ Logged in as you@yourcompany.com. Token saved to profile 'default'.
```

**Confirm the connection:**

Run this command to verify everything is working:

```
retailops-cli auth whoami
```

`whoami` asks the server who you are signed in as, then prints both that identity and your local connection details:

```
  User    : you@yourcompany.com (id=4)
  Name    : Your Name
  Role    : Manager
  Profile : default
  Base URL: http://retailops.yourcompany.com/api/v1
  Token   : 9944b091...
```

The **Role** line tells you which actions you are allowed to perform — Staff, Manager, or Admin (see [Section 1 — Before You Begin](#1-before-you-begin)).

You are now set up and ready to use RetailOps CLI.

> **Connecting to multiple servers:** If your organisation has more than one RetailOps server (for example, a test server and a live server), you can save multiple connections using profiles. See [Common Tasks — Switching Between Connections](#switching-between-connections) for details.

---

## 5. Understanding the Basics

### How commands are structured

Every `retailops-cli` command follows this pattern:

```
retailops-cli  [group]  [action]  [options]
 |      |        |          |
 |      |        |          └── Extra details (filters, IDs, values)
 |      |        └── What to do (list, get, create, update...)
 |      └── What area to work in (orders, inventory, customers...)
 └── The program name
```

**Example:**

```
retailops-cli inventory list --product 42 --from 2024-01-01
```

- `retailops-cli` — run the RetailOps program
- `inventory` — work with inventory
- `list` — show a list
- `--product 42` — filter to product with ID 42
- `--from 2024-01-01` — only show records from this date onwards

### Getting help at any time

Every command has built-in help. If you are unsure what options are available, add `--help` to any command:

```
retailops-cli --help
retailops-cli orders --help
retailops-cli orders create --help
```

This will show a description of the command and all available options, without actually running anything.

### Reading the output

Most commands display results as a table. For example, `retailops-cli customers list` might show:

```
 id   email                  first_name   last_name   created_at
 ─────────────────────────────────────────────────────────────────
 12   alice@acmecorp.com     Alice        Smith       2024-01-10
 13   bob@widgets.co         Bob          Jones       2024-01-15

Total: 2
```

- Each **row** is one record (one customer, one order, etc.)
- Each **column** is a piece of information about that record
- The **ID** column is important — you use the ID number when you want to refer to a specific record in other commands

### Long lists — pages of results

When a list has many records, results are shown 25 at a time. You will see a footer like:

```
Page 1 of 4  (87 total)   use --page 2 for next
```

To see the next page:

```
retailops-cli orders list --page 2
```

To get all records at once:

```
retailops-cli orders list --all
```

> **Tip:** Getting all records at once may be slow if there are thousands of them. Use filters (like `--from` and `--to` for dates) to narrow things down first.

### Confirmation prompts

Commands that make permanent changes (creating, deleting, adjusting stock) will ask you to confirm before doing anything:

```
Record adjustment of +50 units for product 5? [Y/n]:
```

- Press **Enter** or type `y` and press **Enter** to proceed.
- Type `n` and press **Enter** to cancel.

If you are running commands in a script or batch process and want to skip these prompts, add `--yes` (or `-y`) before the group name:

```
retailops-cli --yes inventory adjust --product-id 5 --quantity 50
```

### Previewing a command before it runs (--dry-run)

For commands that make changes you cannot easily undo (refunds, deletions, deactivations, stock adjustments), you can preview what the command **would** do without actually doing it. Add `--dry-run` before the group name:

```
retailops-cli --dry-run --yes orders refund 88
```

You will see something like:

```
DRY RUN — request was not sent.
  POST orders/88/refund/
```

No data is changed on the server. When you are happy that the command is right, run it again without `--dry-run`. This works for: `orders refund`, `orders cancel`, `customers delete`, `users deactivate`, `inventory adjust`, and `inventory bulk-adjust`.

### Output formats

By default, results are shown as a friendly table. You can also ask for other formats — useful for saving data to a file or feeding into other tools:

| Flag | Format | Best for |
|---|---|---|
| `--output table` (default) | Coloured table on screen | Reading at a glance |
| `--output json` | JSON | Feeding into other tools, scripts |
| `--output yaml` | YAML | Configuration files, human-readable backups |
| `--output csv` | Plain CSV | Spreadsheets (Excel, Google Sheets) |

See [Saving output to a file](#saving-output-to-a-file) for examples.

---

## 6. Typical Daily Workflow

This section walks through the most common tasks in a typical working day, with real examples you can follow along with.

---

### 6.1 Checking Inventory

#### See all products with low stock

```
retailops-cli products list --stock low
```

You will see a table of products where the stock level is running low. This uses the threshold set in your system configuration.

To see products that are completely out of stock:

```
retailops-cli products list --stock out
```

To see all products regardless of stock level:

```
retailops-cli products list --stock all
```

#### Filter products by unit of measure

Each product is sold in a particular unit (`piece`, `kg`, `liter`, `meter`, `box`, or `pack`). To narrow the list to one of these:

```
retailops-cli products list --unit kg
retailops-cli products list --unit piece
```

You can combine this with other filters, for example to see only kg-based products that are running low:

```
retailops-cli products list --unit kg --stock low
```

#### Show only active or only inactive products

By default the list includes products of any status. To narrow it:

```
retailops-cli products list --active        # only currently-active products
retailops-cli products list --inactive      # only retired / hidden products
```

Omitting both flags includes everything.

#### See recent inventory movements

Inventory movements are a record of every stock change — sales, purchases, adjustments, and returns.

To see all movements today (replace the date with today's date):

```
retailops-cli inventory list --from 2024-06-15
```

To narrow it down to a specific product (use the product's ID number):

```
retailops-cli inventory list --product 42
```

To see a date range:

```
retailops-cli inventory list --from 2024-06-01 --to 2024-06-15
```

To filter by type of movement:

```
retailops-cli inventory list --type adjustment
retailops-cli inventory list --type sale
retailops-cli inventory list --type purchase
retailops-cli inventory list --type return
```

#### See the full movement history for one product

```
retailops-cli products movements 42
```

Replace `42` with the product's ID number. This shows every stock change for that product, oldest to newest.

#### Check the details of a specific product

If you know a product's ID:

```
retailops-cli products get 42
```

This shows all details for that product, including its current stock level.

---

### 6.2 Managing Orders

Orders move through a set of stages from creation to delivery. Here is the full journey:

```
Draft → Pending → Confirmed → Paid → Shipped → Delivered
```

At the Confirmed stage, an order can also be **Cancelled**. At the Paid stage, it can be **Refunded**.

The following example walks through creating and processing an order from start to finish.

#### Step 1 — Find the customer's ID

Before creating an order, you need the customer's ID number. If you do not know it, search by name:

```
retailops-cli customers list --search "Acme"
```

You will see results like:

```
 id   email                  first_name   last_name
 ────────────────────────────────────────────────────
 12   alice@acmecorp.com     Alice        Smith
```

The ID is **12**. Note this down.

#### Step 2 — Find the product ID(s)

Search for the product you want to add to the order:

```
retailops-cli products list --search "Widget"
```

```
 id   name              price    stock_quantity
 ────────────────────────────────────────────────
 5    Standard Widget   29.99    150
```

The product ID is **5**. Note this down.

#### Step 3 — Create the order

```
retailops-cli orders create --customer-id 12 --items '[{"product_id": 5, "quantity": 3}]'
```

Breaking this down:
- `--customer-id 12` — the customer's ID
- `--items '[...]'` — a list of products and quantities

The items list follows a specific format. For one product:

```json
[{"product_id": 5, "quantity": 3}]
```

For multiple products:

```json
[{"product_id": 5, "quantity": 3}, {"product_id": 8, "quantity": 1}]
```

You should see:

```
✓ Order 88 created (status=Draft, total=89.97).
```

The order has been created with ID **88** and is in **Draft** status. Nothing has been committed yet — you can still make changes.

> **Tip — Specifying a custom price:** By default, the order uses the product's current listed price. To override the price for a specific line item, add `"unit_price": "25.00"` inside that item's braces:
> ```
> [{"product_id": 5, "quantity": 3, "unit_price": "25.00"}]
> ```

> **Tip — Loading items from a file:** Long item lists can be awkward to type on a single line. You can put them in a text file (for example `order-items.json`) and reference the file with `@`:
> ```
> retailops-cli orders create --customer-id 12 --items @order-items.json
> ```
> You can also pipe the items in from another program by using a single dash:
> ```
> Get-Content order-items.json | retailops-cli orders create --customer-id 12 --items -    # Windows PowerShell
> cat order-items.json | retailops-cli orders create --customer-id 12 --items -            # macOS / Linux
> ```

#### Step 4 — Review and update the order (optional)

To see the order you just created:

```
retailops-cli orders get 88
```

If you need to change the items before submitting (for example, to change a quantity):

```
retailops-cli orders update 88 --items '[{"product_id": 5, "quantity": 5}]'
```

> **Warning:** Using `--items` on an update **replaces all items** in the order. Include every product you want in the order, not just the ones you are changing.

You can only update an order while it is in **Draft** status. Once it has been submitted, the items are locked.

#### Step 5 — Submit the order

Submitting moves the order from **Draft** to **Pending**, sending it for manager approval.

```
retailops-cli orders submit 88
```

You will be asked to confirm:

```
Submit order 88 (Draft → Pending)? [Y/n]:
```

Press **Enter** to proceed.

```
✓ Order 88 submitted (status=Pending).
```

#### Step 6 — Confirm the order *(Manager access required)*

Confirming the order moves it from **Pending** to **Confirmed** and deducts the items from stock.

```
retailops-cli orders confirm 88
```

```
✓ Order 88 confirmed (status=Confirmed).
```

#### Step 7 — Record a payment

Once an order is Confirmed, you can record a payment against it.

```
retailops-cli payments record --order 88 --amount 89.97 --method bank_transfer
```

Available payment methods: `cash` · `bank_transfer` · `card` · `check` · `other`

```
✓ Payment of 89.97 recorded for order 88 (method=bank_transfer).
```

When the total payments recorded reach or exceed the order total, the order automatically moves to **Paid** status.

#### Step 8 — Mark as shipped

Once an order is Paid, you can mark it as shipped:

```
retailops-cli orders ship 88
```

```
✓ Order 88 marked as shipped (status=Shipped).
```

#### Step 9 — Mark as delivered

When the customer receives their goods:

```
retailops-cli orders deliver 88
```

```
✓ Order 88 marked as delivered (status=Delivered).
```

The order is now complete.

---

#### Cancelling an order *(Manager access required)*

If a Confirmed order needs to be cancelled (stock is automatically restored):

```
retailops-cli orders cancel 88
```

You will be asked to confirm. Type `y` and press Enter.

---

#### Processing multiple orders at once *(Manager access required)*

If you have several orders waiting at the same stage, you can process them all in one command:

```
retailops-cli orders bulk-confirm --id 88 --id 89 --id 90
```

```
retailops-cli orders bulk-ship --id 88 --id 89 --id 90
```

```
retailops-cli orders bulk-deliver --id 88 --id 89 --id 90
```

Each order is processed independently. If one fails (for example, because it is in the wrong status), the others still go through. You will see a summary of what succeeded and what failed.

---

#### Listing and filtering orders

To see all orders:

```
retailops-cli orders list
```

To filter by status:

```
retailops-cli orders list --status pending
retailops-cli orders list --status confirmed
retailops-cli orders list --status paid
```

To see orders for a specific customer:

```
retailops-cli orders list --customer 12
```

To see orders in a date range:

```
retailops-cli orders list --from 2024-06-01 --to 2024-06-30
```

---

### 6.3 Recording a Stock Adjustment

Use stock adjustments when stock changes outside of the normal order process — for example, when a new shipment arrives, or when goods are damaged and need to be written off.

#### Adding stock (e.g. a new shipment arrived)

Use a **positive** number to add stock:

```
retailops-cli inventory adjust --product-id 5 --quantity 50 --notes "Weekly restock from Supplier A"
```

You will see:

```
Record adjustment of +50 units for product 5? [Y/n]:
```

Press **Enter** to confirm.

```
✓ Adjustment recorded (movement id=201, qty=+50).
```

#### Removing stock (e.g. damaged goods)

Use a **negative** number to deduct stock:

```
retailops-cli inventory adjust --product-id 5 --quantity -3 --notes "3 units damaged in transit"
```

```
Record adjustment of -3 units for product 5? [Y/n]:
```

Press **Enter** to confirm.

```
✓ Adjustment recorded (movement id=202, qty=-3).
```

> **Note:** The `--notes` option is optional but strongly recommended. Notes create a clear audit trail, making it easier to understand why stock levels changed when reviewing history later.

#### Adjusting stock for multiple products at once *(Manager access required)*

```
retailops-cli inventory bulk-adjust --adjustments '[
  {"product_id": 5, "quantity": 50, "notes": "Weekly restock"},
  {"product_id": 8, "quantity": -2, "notes": "Damaged in storage"}
]'
```

Each product is processed independently. You will see a summary of successes and any failures.

> **Tip — Loading adjustments from a file:** For long restock lists, put the JSON in a text file and reference it with `@`:
> ```
> retailops-cli inventory bulk-adjust --adjustments @restock.json
> ```
> Or pipe it from another program using a single dash:
> ```
> Get-Content restock.json | retailops-cli inventory bulk-adjust --adjustments -    # Windows PowerShell
> cat restock.json | retailops-cli inventory bulk-adjust --adjustments -            # macOS / Linux
> ```

> **Tip — Preview before committing:** Add `--dry-run` to see exactly what the command would send without actually changing any stock:
> ```
> retailops-cli --dry-run inventory bulk-adjust --adjustments @restock.json
> ```

---

### 6.4 Looking Up a Customer

#### Search for a customer by name or email

```
retailops-cli customers list --search "Smith"
retailops-cli customers list --search "acmecorp.com"
```

#### View full details for a customer

```
retailops-cli customers get 12
```

#### View all orders for a customer

```
retailops-cli orders list --customer 12
```

#### View all payments for a customer's orders

First find the order IDs with `retailops-cli orders list --customer 12`, then:

```
retailops-cli payments list --order 88
```

---

## 7. Common Tasks

### Adding a new customer

The simplest way is to run `retailops-cli customers create` and let it prompt you for the essentials:

```
retailops-cli customers create
```

You will see prompts only for the **required** fields:

```
First name: Alice
Last name: Smith
Email: alice@acmecorp.com
```

After answering those three, the customer is created:

```
✓ Customer 'Alice Smith' created (id=12).
```

If you want to fill in additional details (phone, address, ID number, date of birth, etc.) at the same time, supply them as flags. All flags are optional:

| Flag | What it sets |
|---|---|
| `--phone "..."` | Phone number |
| `--national-id "..."` | National / tax ID (must be unique across customers if provided) |
| `--dob YYYY-MM-DD` | Date of birth |
| `--gender M` or `--gender F` | Gender (use empty string `""` to clear) |
| `--address "..."` | Street address (line 1) |
| `--address-line-2 "..."` | Apartment, suite, building, etc. |
| `--city "..."` | City |
| `--state "..."` | State / province |
| `--postal-code "..."` | ZIP / postal code |
| `--country "..."` | Defaults to `United States` |
| `--notes "..."` | Free-text internal notes |
| `--user-id N` | Link this customer to a user account |

**Full example:**

```
retailops-cli customers create \
  --first-name Alice --last-name Smith --email alice@acmecorp.com \
  --phone "+1-555-0100" --national-id "V-12345678" --dob 1990-05-15 \
  --gender F --address "123 Main St" --address-line-2 "Apt 4B" \
  --city Springfield --state IL --postal-code 62701 --country "United States"
```

### Updating a customer's details

```
retailops-cli customers update 12 --email newemail@acmecorp.com
retailops-cli customers update 12 --phone "+1-555-0199" --address-line-2 "Suite 200"
retailops-cli customers update 12 --dob 1990-05-15 --gender F
```

Only supply the fields you want to change. Everything else stays the same. The same flags listed above for `create` are accepted on `update`.

### Deleting a customer

```
retailops-cli customers delete 12
```

You will be asked to confirm. To preview what would happen without actually deleting, add `--dry-run`:

```
retailops-cli --dry-run customers delete 12
```

> **Note:** A customer cannot be deleted if they have any orders on record. You will see an error message if you try.

---

### Adding a new product *(Manager access required)*

```
retailops-cli products create
```

You will be prompted for name, description, price, stock quantity, and category.

Active products need an image source. You can upload a local file:

```
retailops-cli products create --sku SKU-1 --name "Running Shoes" --category-id 2 --unit piece --price 59.99 --image .\shoe.jpg
```

Or use an external image URL:

```
retailops-cli products create --sku SKU-2 --name "Notebook" --category-id 2 --unit piece --price 4.99 --external-image-url "https://example.com/notebook.jpg"
```

### Updating a product *(Manager access required)*

```
retailops-cli products update 5 --price 34.99
retailops-cli products update 5 --name "Premium Widget"
retailops-cli products update 5 --image .\replacement.jpg
retailops-cli products update 5 --clear-image --clear-external-image-url
```

Supply only the fields you want to change.

---

### Viewing payment history

To see all payments:

```
retailops-cli payments list
```

To filter by order:

```
retailops-cli payments list --order 88
```

To filter by payment method:

```
retailops-cli payments list --payment-method bank_transfer
retailops-cli payments list --method mobile_payment
```

To filter modern receipt payments:

```
retailops-cli payments list --status pending_review
retailops-cli payments list --has-receipt
retailops-cli payments list --bank "BDV"
```

To filter by date:

```
retailops-cli payments list --from 2024-06-01 --to 2024-06-30
```

To record a receipt-backed payment with OCR metadata already verified by the API:

```
retailops-cli payments record --order 88 --amount 1.98 --method mobile_payment --ref 005901670379 --transaction-key txn-005901670379 --origin-bank BDV --recipient-bank Bancamiga --receipt-image .\receipt.jpg
```

To ask RetailOps to verify a receipt image through the configured OCR provider:

```
retailops-cli payments verify-receipt --image .\receipt.jpg --method mobile_payment --expected-amount-usd 1.98 --expected-reference 005901670379 --expected-paid-on 2026-05-03 --expected-origin-bank BDV
```

The CLI does not run OCR locally. It uploads the image to the RetailOps API, and the API calls the configured OCR provider.

To check OCR provider health:

```
retailops-cli payments receipt-healthz
```

---

### Viewing or changing system settings *(Manager access required)*

System currency settings control how money is displayed everywhere — symbol, decimal places, and an optional secondary currency that appears alongside the primary one (useful when prices are quoted in one currency but customers think in another).

**View the current settings:**

```
retailops-cli settings get
```

You will see something like:

```
 currency_code             : USD
 currency_symbol           : $
 decimal_places            : 2
 secondary_currency_enabled: True
 secondary_currency_code   : VES
 secondary_currency_symbol : Bs.
 secondary_decimal_places  : 2
 secondary_exchange_rate   : 36.50000000
```

**Change the primary currency:**

```
retailops-cli settings update --currency-code EUR --currency-symbol "€" --decimal-places 2
```

**Enable a secondary currency** (e.g. show Bolívares alongside US Dollars at a fixed rate):

```
retailops-cli settings update --secondary-enabled \
  --secondary-code VES --secondary-symbol "Bs." \
  --secondary-decimal-places 2 --secondary-rate 36.50
```

**Update only the exchange rate** (everything else stays the same):

```
retailops-cli settings update --secondary-rate 38.10
```

**Turn the secondary currency off** (the other secondary fields are kept on file but ignored until re-enabled):

```
retailops-cli settings update --no-secondary-enabled
```

> **Note:** The exchange rate is a static value you set — it does not auto-update. Change it whenever you want the displayed conversions to reflect the current market.

---

**Enable OCR for receipt methods:**

```
retailops-cli settings update --ocr-enabled --ocr-base-url "https://vepay-api.example.com" --ocr-enabled-method mobile_payment --ocr-enabled-method bank_transfer --receipt-image-required
```

**Set or clear the OCR API key:**

```
retailops-cli settings update --ocr-api-key "secret-value"
retailops-cli settings update --clear-ocr-api-key
```

Only pass `--ocr-api-key` when you want to change the stored key. `retailops-cli settings get` masks existing keys.

---

### Kiosk API checks

Kiosk commands use a station key, not your user token. Pass it each time or set `RETAILOPS_KIOSK_API_KEY`.

```
retailops-cli kiosk heartbeat --kiosk-key KIOSK_KEY
retailops-cli kiosk products --search shoes
retailops-cli kiosk product-lookup SKU-1
retailops-cli kiosk identify --national-id V30759313
```

Checkout accepts JSON for line items and optional receipt metadata:

```
retailops-cli kiosk checkout --customer-id 5 --items '[{"sku":"SKU-1","quantity":2}]' --payment-reference 005901670379 --payment-method mobile_payment --receipt @receipt.json
```

---

### API schema helpers

```
retailops-cli schema get --format yaml
retailops-cli schema get --format json
retailops-cli schema swagger-url
retailops-cli schema redoc-url
```

---

### Checking your configuration

If a command behaves unexpectedly — talks to the wrong server, uses an old token, or seems to have lost your settings — `retailops-cli auth config` shows you exactly what `retailops-cli` is using and where each value came from:

```
retailops-cli auth config
```

You will see a table like:

```
 Profile     default        settings.active_profile
 Base URL    http://...     config file
 Token       9944b091...    config file
 Timeout     30.0s          default
 Verify SSL  Yes            config file
 Config path C:\Users\You\AppData\Roaming\retailops\config.toml
```

The third column tells you whether each setting came from a `--profile` flag, an environment variable, the config file, or the built-in default. This is the fastest way to confirm "yes, I really am pointing at the production server" before running a destructive command.

---

### Previewing a command before running it

If you are about to run a destructive command (refund, delete, deactivate, large stock adjustment) and want to confirm what it will actually send to the server, prefix it with `--dry-run`:

```
retailops-cli --dry-run --yes customers delete 12
retailops-cli --dry-run --yes orders refund 88
retailops-cli --dry-run inventory adjust --product-id 5 --quantity 50
retailops-cli --dry-run inventory bulk-adjust --adjustments @restock.json
```

You will see the exact request that would have been sent (method, path, body) but **nothing happens on the server**. When the preview looks right, run the same command again without `--dry-run`.

`--dry-run` is supported by: `orders refund`, `orders cancel`, `customers delete`, `users deactivate`, `inventory adjust`, `inventory bulk-adjust`.

---

### Resetting a forgotten password

If you cannot log in because you have forgotten your password, run this from a terminal (you do not need to be logged in):

```
retailops-cli auth passwd-reset --email you@yourcompany.com --url YOUR_SERVER_ADDRESS
```

You will receive a password reset email. Follow the link in the email, or use the confirmation command if your administrator provides you with the required codes:

```
retailops-cli auth passwd-reset-confirm --uid XXXXXXXX --token XXXXXXXXXX --url YOUR_SERVER_ADDRESS
```

You will be prompted to enter and confirm your new password.

---

### Switching between connections

If you connect to more than one RetailOps server (for example, a test environment and your live production system), you can save both as named profiles.

**Log in to a second server under a different profile name:**

```
retailops-cli auth login --url http://test.retailops.yourcompany.com/api/v1 --profile test
```

**Switch your active connection:**

```
retailops-cli auth use test
```

**See all saved connections:**

```
retailops-cli auth profiles
```

**Use a specific profile for just one command (without switching permanently):**

```
retailops-cli --profile test orders list
```

**See which connection you are currently using:**

```
retailops-cli auth whoami
```

---

### Issuing a refund *(Administrator access required)*

Refunds apply to orders that are in **Paid** status. Stock is automatically restored.

```
retailops-cli orders refund 88
```

You will be asked to type the order ID to confirm the action (this extra step prevents accidental refunds):

```
Type the order ID to confirm refund: 88
```

Type `88` and press Enter.

```
✓ Order 88 refunded (status=Refunded).
```

---

### Saving output to a file

If you need to export data for a spreadsheet, a report, or another tool, redirect the output of any list command into a file.

**As a CSV** (best for spreadsheets — Excel, Google Sheets, Numbers):

Windows (PowerShell):
```
retailops-cli orders list --output csv | Out-File -FilePath orders.csv -Encoding utf8
```

macOS / Linux:
```
retailops-cli orders list --output csv > orders.csv
```

**As JSON** (best for feeding into other tools or scripts):

```
retailops-cli orders list --output json > orders.json
```

**As YAML** (best for human-readable backups or hand-editing):

```
retailops-cli settings get --output yaml > currency-settings.yaml
```

The file will be saved in whichever folder your terminal is currently in. To grab everything (not just the first page), add `--all`:

```
retailops-cli orders list --all --output csv > all-orders.csv
```

---

## 8. Troubleshooting

### Error messages explained

| What you see | What it means | What to do |
|---|---|---|
| `Error: Connection refused` or `Could not connect to ...` | The tool cannot reach the RetailOps server | Check your internet connection; confirm the server address with your IT administrator |
| `Error 401: Unauthorized` | You are not logged in, or your session has expired | Run `retailops-cli auth login --url YOUR_SERVER_ADDRESS` to log in again |
| `Error 403: Permission denied` | Your account does not have access to this feature | Contact your administrator to check your role (Staff, Manager, or Admin) |
| `Error 404: Not found` | The record you referenced does not exist | Double-check the ID number |
| `Error 409: Conflict` | The action cannot be completed due to a conflict (e.g. deleting a customer who has orders) | Read the error message for specifics; some restrictions cannot be overridden |
| `Error 400: Bad request` | One of the values you supplied is invalid | Read the error message — it usually tells you exactly which field has a problem |
| `Quantity cannot be zero` | You tried to record a zero stock adjustment | Enter a positive number to add stock, or a negative number to remove it |
| `retailops-cli: command not found` | The installation did not complete, or the terminal needs to be restarted | Close the terminal, open a new one, and try `retailops-cli --help` again. If still failing, repeat the installation steps. |
| `No fields supplied. Nothing to update.` | You ran an update command without specifying any changes | Add at least one option to the update command (e.g. `--email` or `--name`) |
| A confirmation prompt that will not go away | The terminal is waiting for your input | Type `y` and press Enter to proceed, or type `n` and press Enter to cancel |

---

### The tool is slow or stops responding

If a command takes a very long time or appears to freeze:

- Press **Ctrl + C** to cancel it. The terminal will return to a blinking cursor.
- Try the command again with a filter to reduce the amount of data (for example, add `--from 2024-06-01` to date-filter a long list).
- If the problem persists, contact your IT administrator — the server may be temporarily unavailable.

---

### Seeing more detail about what went wrong

If a command fails and the error message is not clear, you can run it again with the `--verbose` flag to see the full communication between the tool and the server. Share this output with your IT administrator for diagnosis:

```
retailops-cli --verbose orders list
```

The extra detail will appear in a different colour (or labelled `[REQUEST]` and `[RESPONSE]`) so it is easy to tell apart from the normal output.

---

### "Why is retailops-cli using the wrong server / token / profile?"

If `retailops-cli` seems to be talking to the wrong server, or you have set environment variables and are not sure whether they are taking effect, run:

```
retailops-cli auth config
```

This shows the current profile, server URL, token preview, and — most usefully — **where each value came from** (a `--profile` flag, an environment variable, the saved config file, or the built-in default). It is the quickest way to verify your setup before running anything important. See [Section 7 — Checking your configuration](#checking-your-configuration) for full details.

---

### Rate limit warnings

The server limits how many certain actions you can perform per minute to prevent overload. If you hit a limit, the tool will automatically pause and retry — you will see a message like:

```
Rate limited. Retrying in 12 seconds...
```

You do not need to do anything. The command will complete on its own. If it keeps happening frequently, spread your actions out over a longer period.

---

## 9. Logging Out

To log out of your current session and remove your saved credentials from this computer:

```
retailops-cli auth logout
```

You will see:

```
✓ Logged out. Token removed from profile 'default'.
```

After logging out, you will need to run `retailops-cli auth login` again to use the tool.

> **When to log out:** You do not need to log out at the end of every day — your session persists across terminal windows and restarts. Log out if you are stepping away from a shared computer, if your credentials have been compromised, or if your account is being deactivated.

---

## Appendix A — Glossary

**API**
The interface that `retailops-cli` uses to communicate with the RetailOps server. You do not need to interact with it directly — the tool handles everything for you.

**Command**
A line of text that you type into the terminal and run by pressing Enter. For example: `retailops-cli orders list`.

**CSV**
A file format (Comma-Separated Values) that can be opened in spreadsheet applications like Microsoft Excel or Google Sheets. Use `--output csv` to export data in this format.

**Flag / Option**
An extra instruction added to a command to customise its behaviour. Flags start with `--` (for example, `--from`, `--output`, `--all`). Some flags also have short versions starting with `-` (for example, `-o` instead of `--output`).

**ID**
A unique number that identifies a record in the system. Every customer, product, order, and payment has its own ID. You use the ID when you want to refer to a specific record in a command.

**JSON**
A format used to pass structured data in some commands (particularly `--items` for orders). It uses square brackets `[]` and curly braces `{}` with field names in quotes. The guide provides templates you can copy and fill in — you do not need to understand the format in depth.

**Page / Pagination**
When there are too many results to show at once, they are split into pages of 25. Use `--page 2`, `--page 3`, etc. to navigate between pages, or `--all` to retrieve everything at once.

**Profile**
A saved connection to a RetailOps server, including the server address and your login credentials. Most users only ever have one profile (called `default`). Users who work with multiple servers can create additional profiles with names of their choice.

**Role**
Your access level within RetailOps. There are three roles:
- **Staff** — can view records and manage orders through the submission, shipping, and delivery stages
- **Manager** — everything Staff can do, plus write access to products, categories, and inventory, and the ability to confirm and cancel orders
- **Admin** — everything Manager can do, plus user management and the ability to issue refunds

**Terminal**
The text-based window where you type commands. Also called a command prompt, command line, console, or shell depending on the operating system.

**Token**
A long string of letters and numbers that identifies your logged-in session. It is stored automatically when you log in and sent with every command to prove your identity. You should treat it like a password — do not share it with others.

---

## Appendix B — Quick Reference Card

Cut out or print this page for quick access to the most common commands.

---

### Getting started

| Task | Command |
|---|---|
| Log in | `retailops-cli auth login --url YOUR_SERVER_ADDRESS` |
| Check who you are logged in as | `retailops-cli auth whoami` |
| Show your current configuration (profile, URL, token, sources) | `retailops-cli auth config` |
| Install tab completion (one-time) | `retailops-cli --install-completion` |
| Log out | `retailops-cli auth logout` |

### Inventory

| Task | Command |
|---|---|
| See low-stock products | `retailops-cli products list --stock low` |
| See out-of-stock products | `retailops-cli products list --stock out` |
| Filter by unit of measure | `retailops-cli products list --unit kg` |
| Show only active or only inactive products | `retailops-cli products list --active` · `retailops-cli products list --inactive` |
| View product details | `retailops-cli products get ID` |
| Create product with uploaded image | `retailops-cli products create ... --image path.jpg` |
| Create product with external image | `retailops-cli products create ... --external-image-url URL` |
| View stock movement history for a product | `retailops-cli products movements ID` |
| See all inventory movements | `retailops-cli inventory list` |
| Filter movements by product | `retailops-cli inventory list --product ID` |
| Filter movements by date | `retailops-cli inventory list --from YYYY-MM-DD` |
| Add stock (adjustment) | `retailops-cli inventory adjust --product-id ID --quantity N --notes "reason"` |
| Remove stock (adjustment) | `retailops-cli inventory adjust --product-id ID --quantity -N --notes "reason"` |
| Bulk adjust from a file *(Manager)* | `retailops-cli inventory bulk-adjust --adjustments @file.json` |

### Orders

| Task | Command |
|---|---|
| List all orders | `retailops-cli orders list` |
| Filter orders by status | `retailops-cli orders list --status pending` |
| View order details | `retailops-cli orders get ID` |
| Create an order | `retailops-cli orders create --customer-id ID --items '[{"product_id": ID, "quantity": N}]'` |
| Create an order from a file | `retailops-cli orders create --customer-id ID --items @items.json` |
| Submit an order | `retailops-cli orders submit ID` |
| Confirm an order *(Manager)* | `retailops-cli orders confirm ID` |
| Cancel an order *(Manager)* | `retailops-cli orders cancel ID` |
| Ship an order | `retailops-cli orders ship ID` |
| Deliver an order | `retailops-cli orders deliver ID` |
| Refund an order *(Admin)* | `retailops-cli orders refund ID` |
| Bulk confirm / ship / deliver *(Manager)* | `retailops-cli orders bulk-confirm --id N --id N ...` |

### Payments

| Task | Command |
|---|---|
| Record a payment | `retailops-cli payments record --order ID --amount AMOUNT --method METHOD` |
| View payments for an order | `retailops-cli payments list --order ID` |
| Verify a receipt through OCR | `retailops-cli payments verify-receipt --image path.jpg --method mobile_payment --expected-amount-usd AMOUNT` |
| Check OCR provider health | `retailops-cli payments receipt-healthz` |

### Customers

| Task | Command |
|---|---|
| Search for a customer | `retailops-cli customers list --search "name"` |
| View customer details | `retailops-cli customers get ID` |
| Create a customer (basic) | `retailops-cli customers create` |
| Create with extended fields | `retailops-cli customers create --first-name X --last-name Y --email X@Y.Z --national-id "..." --dob YYYY-MM-DD --gender F --address "..." --address-line-2 "..."` |
| Update one or more fields | `retailops-cli customers update ID --field VALUE` |

### System settings *(Manager)*

| Task | Command |
|---|---|
| View current settings | `retailops-cli settings get` |
| Change primary currency | `retailops-cli settings update --currency-code EUR --currency-symbol "€"` |
| Enable secondary currency | `retailops-cli settings update --secondary-enabled --secondary-code VES --secondary-symbol "Bs." --secondary-rate 36.50` |
| Update the exchange rate only | `retailops-cli settings update --secondary-rate 38.10` |
| Disable secondary currency | `retailops-cli settings update --no-secondary-enabled` |
| Enable receipt OCR | `retailops-cli settings update --ocr-enabled --ocr-enabled-method mobile_payment --receipt-image-required` |

### Kiosk and schema

| Task | Command |
|---|---|
| Kiosk heartbeat | `retailops-cli kiosk heartbeat --kiosk-key KEY` |
| Kiosk product lookup | `retailops-cli kiosk product-lookup SKU` |
| Kiosk checkout | `retailops-cli kiosk checkout --customer-id ID --items JSON --payment-reference REF` |
| Download OpenAPI schema | `retailops-cli schema get --format yaml` |
| Show Swagger URL | `retailops-cli schema swagger-url` |

### Useful options (add before the group name)

| Option | What it does |
|---|---|
| `--yes` or `-y` | Skip all confirmation prompts |
| `--dry-run` | Preview the request without sending it (delete / refund / cancel / deactivate / adjust commands) |
| `--output csv` | Output results as CSV (best for spreadsheets) |
| `--output json` | Output results as JSON (best for scripts) |
| `--output yaml` | Output results as YAML (best for human-readable backups) |
| `--verbose` or `-v` | Show detailed request/response information for troubleshooting |
| `--all` | Retrieve all pages of results at once |
| `--profile NAME` | Use a specific saved connection for one command |
| `--help` | Show help for any command |

**Payment methods:** `cash` · `mobile_payment` · `bank_transfer` · `card` · `check` · `other`

**Order statuses:** `draft` · `pending` · `confirmed` · `paid` · `shipped` · `delivered` · `cancelled` · `refunded`

**Units of measure:** `piece` · `kg` · `liter` · `meter` · `box` · `pack`

**JSON input shorthand:** for `--items` (orders) and `--adjustments` (inventory bulk-adjust), use `@path/to/file.json` to load from a file or `-` to read from a pipe.
