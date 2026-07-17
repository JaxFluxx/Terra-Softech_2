# Referral Bypass — Dataset Guide (Step 1)

**Audience:** Data analyst  
**Purpose:** Explain the datasets shared for identifying **referral bypass** — cases where a user submitted a referral, and the referred person later appears as a booking that was **not** marked/credited as a referral (i.e. treated as a fresh booking).  
**Scope of this document:** **Step 1 only** — understanding the base extract datasets. Detection / matching logic is out of scope here.

---

## 1. What you are receiving

Two flat extracts (CSV/Excel/SQL dump — format may vary by client):

| Dataset | Filename suggestion | Grain (one row =) | Contents |
|--------|---------------------|-------------------|----------|
| **Referral submissions** | `referrals_extract` | One referral enquiry | Every active referral lead submitted in the system, plus whether that **same enquiry** later got a booking |
| **Bookings** | `bookings_extract` | One booking | Every non-canceled booking with its enquiry, lead, project, and source context |

Together these let you reconstruct:

- Who referred whom, when, and for which project  
- Which bookings exist and how they are attributed (referral vs non-referral)  
- Whether a referred person later booked under a different path  

Run/share **per client database** if multiple tenants exist. Do not mix client files without a `client` column.

---

## 2. Business context (short)

### Core concepts

| Concept | Meaning |
|--------|---------|
| **Referrer** | Existing user (customer, influencer, employee, sales manager, etc.) who submits a referral |
| **Lead** | The referred person (prospective buyer) |
| **Enquiry** | Interest record linking a lead to a project and to the user who “owns” that lead in our system (for referrals, the referrer) |
| **Referral enquiry** | An enquiry with `source = REFERRAL` |
| **Booking** | Unit booking; usually linked to an enquiry via `enquiry_id` |
| **Property** | Physical unit; optional context on the booking extract |

### How a normal referral conversion looks

```
Referrer (user)
    └── submits Referral enquiry (source = REFERRAL)
            └── for Lead (referred person) + Project
                    └── later Booking on that same enquiry
                            └── booking source ideally = REFERRAL
```

### What “bypass” means (for later analysis)

Roughly: a referral was submitted, but conversion credit appears on a **non-referral** path (different enquiry, different source, or different project).  

**Agreed rules for later steps (not implemented in these extracts):**

- Exact match on identity fields is enough; **no decryption required**  
- Booking on a **separate project** still counts as bypass  

This Step 1 pack only supplies the raw tables to support that analysis.

---

## 3. Entity relationship (simplified)

```
users (referrer / booking user)
   │
   │ user_id
   ▼
enquires  ──────── lead_id ──────►  leads (referred person)
   │
   │ id
   ▼
bookings  ──────── property_id ──►  properties (optional)
   │
   └── project comes from enquiry.project_id ──► projects
```

| Table (source system) | Role in extracts |
|----------------------|------------------|
| `users` | Referrer; also `bookings.user_id` |
| `leads` | Referred person identity |
| `enquires` | Referral / enquiry record (**note spelling: enquires**) |
| `bookings` | Conversion |
| `projects` | Project name/context |
| `properties` | Unit (only if joined for booking context) |

---

## 4. Dataset A — Referral submissions

### 4.1 Description

All **referral enquiries** that are active and not soft-deleted.

Each row is one referral submission. If that enquiry itself has a valid booking, booking columns are populated; otherwise they are null.

### 4.2 Filters already applied in the extract

| Filter | Value |
|--------|--------|
| Enquiry source | `REFERRAL` only |
| Enquiry soft delete | `isDeleted = 0` |
| Enquiry active | `isActive = 1` |
| Lead soft delete | `isDeleted = 0` |
| User (referrer) soft delete | `isDeleted = 0` |
| Booking on referral enquiry (if present) | `isDeleted = 0` and status **not** in `CANCELED`, `BOOKING_REJECTED` |

### 4.3 Field dictionary

| Column | Type (logical) | Description |
|--------|----------------|-------------|
| `referral_enquiry_id` | ID | Primary key of the referral enquiry (`enquires.id`) |
| `referral_enquiry_crm_id` | string | CRM id of the enquiry, if synced |
| `referral_submitted_on` | datetime | When the referral enquiry was created |
| `referral_enquiry_status` | enum string | Lifecycle of this enquiry (see §6) |
| `stage` | string | Optional pipeline stage |
| `source` | enum string | Always `REFERRAL` in this extract |
| `referralSource` | enum string | Who the referrer is in product terms: `CUSTOMER`, `SITE_VISITOR`, `EMPLOYEE`, `INFLUENCER`, `SALES_MANAGER` |
| `referralCode` | string | Referral code if stored |
| `relationToReferrer` | string | Relation of lead to referrer (free text), if provided |
| `sourcePlatform` | enum string | Where the enquiry entered (e.g. app, CRM, website, call center) |
| `project_id` | ID | Project the referral is for |
| `projectName` | string | Project display name |
| `project_crm_id` | string | Project CRM id |
| `referrer_user_id` | ID | User who submitted / owns the referral (`enquires.user_id`) |
| `referrer_name` | string | Referrer display name |
| `referrer_crm_id` | string | Referrer CRM id |
| `referrer_user_type` | enum string | User type of referrer (e.g. `CUSTOMER`, `INFLUENCER`) |
| `lead_id` | ID | Referred person (`leads.id`) — **main join key to bookings via enquiry.lead_id** |
| `lead_name` | string | Lead name (plaintext) |
| `lead_crm_id` | string | Lead CRM id |
| `lead_hash_id` | string | Stable hash identifier for the lead |
| `mobileCountryCode` | int | Country code for lead mobile |
| `mobileNumber` | string | Lead mobile — **encrypted (symmetric)**; use **exact equality** only |
| `email` | string | Lead email — **encrypted (symmetric)**; use **exact equality** only |
| `booking_on_referral_enquiry_id` | ID / null | Booking id if this **same** referral enquiry converted |
| `booking_on_referral_date` | datetime / null | Booking date on that conversion |
| `booking_on_referral_status` | enum string / null | Status of that booking |
| `booking_on_referral_source` | enum string / null | Source stored on that booking |

### 4.4 How to read a row

- **Always:** “User X referred lead Y for project Z on date D.”  
- **If booking columns are filled:** that referral enquiry itself got a booking (attributed path may still need checking via `booking_on_referral_source`).  
- **If booking columns are null:** this referral has **not** converted on its own enquiry (candidate pool for bypass when matched to Dataset B).

---

## 5. Dataset B — Bookings

### 5.1 Description

All **non-canceled** bookings, with optional enquiry/lead/project context.

Each row is one booking. `enquiry_id` / lead fields may be null if the booking was not linked to an enquiry.

### 5.2 Filters already applied in the extract

| Filter | Value |
|--------|--------|
| Booking soft delete | `isDeleted = 0` |
| Booking status | **Excluded:** `CANCELED`, `BOOKING_REJECTED` |
| Joined enquiry/lead | Soft-deleted rows excluded where joined |

### 5.3 Field dictionary

| Column | Type (logical) | Description |
|--------|----------------|-------------|
| `booking_id` | ID | Primary key (`bookings.id`) |
| `booking_crm_id` | string | CRM booking id |
| `bookingDate` | datetime | Business booking date (prefer this over created time for timelines) |
| `booking_created_on` | datetime | System create timestamp |
| `bookingStatus` | enum string | e.g. `BOOKING_DONE`, `REGISTRATION_DONE`, `INVOICE_UPLOADED`, … |
| `booking_source` | enum string | Source on the booking: `REFERRAL`, `CHANNEL_PARTNER`, `DIRECT`, `LOYALTY`, or null |
| `unitNumber` | string | Booked unit number |
| `agreementValue` | number | Agreement value |
| `booking_user_id` | ID | User linked on the booking (often the enquiry owner / referrer / CP — **not always the buyer**) |
| `enquiry_id` | ID / null | Linked enquiry; null = booking without enquiry |
| `enquiry_source` | enum string / null | Source on the linked enquiry |
| `referralSource` | enum string / null | Referral subtype if enquiry is referral |
| `enquiry_created_on` | datetime / null | When linked enquiry was created |
| `enquiry_user_id` | ID / null | Owner of the enquiry (referrer for referral enquiries) |
| `lead_id` | ID / null | Lead on the linked enquiry |
| `project_id` | ID / null | Project from the linked enquiry |
| `projectName` | string / null | Project name |
| `lead_name` | string / null | Lead name |
| `lead_hash_id` | string / null | Lead hash |
| `mobileNumber` | string / null | Lead mobile — **encrypted**; exact match only |
| `email` | string / null | Lead email — **encrypted**; exact match only |
| `property_id` | ID / null | Linked property/unit record if present |

### 5.4 How to read a row

- **`enquiry_source` / `booking_source` = `REFERRAL`:** booking is attributed as referral (at least on that path).  
- **`enquiry_source` in (`DIRECT`, `CHANNEL_PARTNER`, `LOYALTY`) or null:** non-referral attribution — relevant when the same person also appears in Dataset A.  
- **`enquiry_id` null:** booking has no enquiry link; identity join is harder (no `lead_id` on this row).

---

## 6. Important enumerations

### Enquiry / booking source (`source`)

| Value | Meaning |
|-------|---------|
| `REFERRAL` | Referral program |
| `CHANNEL_PARTNER` | Channel partner |
| `DIRECT` | Direct |
| `LOYALTY` | Loyalty |

### Enquiry status (`referral_enquiry_status`) — common values

| Value | Meaning |
|-------|---------|
| `ENQUIRY` | Created / open |
| `SITE_VISIT_BOOKED` | Site visit scheduled |
| `SITE_VISIT_DONE` | Site visit completed |
| `BOOKING_DONE` | Booking done (on enquiry status) |
| `REGISTRATION_DONE` | Registration done |
| `BOOKING_CANCELLED` | Cancelled |
| `LOST` / `REJECTED` | Lost or rejected |
| `INVOICE_UPLOADED` / `INVOICE_PAID` / `REDEEMED` | Post-booking commercial states |

### Booking status (`bookingStatus`) — common values

| Value | In extract? |
|-------|-------------|
| `BOOKING_DONE`, `REGISTRATION_DONE`, `BOOKING_APPLICATION_DONE`, `INVOICE_UPLOADED`, `INVOICE_PAID`, `REDEEMED` | Yes (typically) |
| `CANCELED`, `BOOKING_REJECTED` | **No** — filtered out |

### Referral source (`referralSource`)

| Value | Meaning |
|-------|---------|
| `CUSTOMER` | Existing customer referred |
| `SITE_VISITOR` | Site visitor referred |
| `EMPLOYEE` | Employee referred |
| `INFLUENCER` | Influencer referred |
| `SALES_MANAGER` | Sales manager referred |

---

## 7. Encryption & PII handling

- Fields **`mobileNumber`** and **`email`** (on leads) are stored with **symmetric encryption**.  
- **No decryption is required** for this analysis.  
- Treat values as opaque identifiers:  
  - **Exact equality** (`A.mobileNumber = B.mobileNumber`) is valid for matching **within the same client dataset**.  
  - Do not substring-search, fuzzy-match, or interpret the ciphertext as a phone/email.  
- **`lead_name`** is plaintext and may be used for readability; prefer **`lead_id`** (and exact encrypted mobile) for identity.  
- **`lead_hash_id`** is a stable opaque id useful for joins/dedup within system rules.

---

## 8. Recommended joins between the two datasets

These are **for understanding** the model; full bypass detection is a later step.

| Goal | Join |
|------|------|
| Same person via system lead | `referrals.lead_id` = `bookings.lead_id` |
| Same person via encrypted mobile (different lead rows) | `referrals.mobileNumber` = `bookings.mobileNumber` (exact; both non-null) |
| Same referral enquiry’s own booking | `referrals.referral_enquiry_id` = `bookings.enquiry_id` |
| Timeline | Compare `referrals.referral_submitted_on` ≤ `bookings.bookingDate` (fallback: `booking_created_on`) |
| Project scope | Compare `referrals.project_id` vs `bookings.project_id` — **same or different both matter** for bypass |

### Row interpretation examples

| Situation | What it suggests |
|-----------|------------------|
| Referral row with booking columns filled | Conversion on the referral enquiry path |
| Referral row with null booking columns + later booking for same `lead_id` with non-`REFERRAL` `enquiry_source` | Strong candidate for bypass (any project) |
| Same `lead_id`, different `project_id` on booking | Still in scope as bypass per business rule |
| Booking with null `enquiry_id` | Cannot join on `lead_id`; limited use unless other keys exist |

---

## 9. Data quality notes

1. **Table spelling:** source table is `enquires`, not `enquiries`.  
2. **Soft deletes:** extracts already exclude deleted/inactive rows as listed above.  
3. **One lead, many enquiries:** the same `lead_id` can appear in multiple referral rows and multiple booking rows.  
4. **One enquiry, one booking:** booking is typically 1:1 with enquiry when linked.  
5. **`booking_user_id` ≠ buyer always:** for referrals it is often the referrer (enquiry owner), not the lead. Use **lead** fields for the referred person.  
6. **Multi-tenant:** do not join encrypted mobiles across different client exports.  
7. **Null sources:** null `booking_source` / `enquiry_source` should be treated as **not marked as referral** unless confirmed otherwise.  
8. **CRM ids:** useful for ops validation; not always populated for app-only records.

---

## 10. What this Step 1 pack is *not*

- Not a pre-built list of confirmed bypass cases  
- Not decrypted PII  
- Not a full warehouse model (no activities, invoices, reward audits, etc.)  
- Not cross-client merged data  

Use these two datasets as the **working base** for matching and classification in subsequent analysis steps.

---

## 11. SQL used to generate the extracts (reference)

### 11.1 Referrals extract

```sql
SELECT
    e.id                    AS referral_enquiry_id,
    e.crmId                 AS referral_enquiry_crm_id,
    e.createdOn             AS referral_submitted_on,
    e.status                AS referral_enquiry_status,
    e.stage,
    e.source,
    e.referralSource,
    e.referralCode,
    e.relationToReferrer,
    e.sourcePlatform,
    e.project_id,
    p.projectName,
    p.crmId                 AS project_crm_id,
    e.user_id               AS referrer_user_id,
    u.name                  AS referrer_name,
    u.crmId                 AS referrer_crm_id,
    u.type                  AS referrer_user_type,
    e.lead_id,
    l.name                  AS lead_name,
    l.crmId                 AS lead_crm_id,
    l.hashId                AS lead_hash_id,
    l.mobileCountryCode,
    l.mobileNumber,
    l.email,
    b.id                    AS booking_on_referral_enquiry_id,
    b.bookingDate           AS booking_on_referral_date,
    b.bookingStatus         AS booking_on_referral_status,
    b.source                AS booking_on_referral_source
FROM enquires e
JOIN leads l     ON l.id = e.lead_id AND l.isDeleted = 0
JOIN users u     ON u.id = e.user_id AND u.isDeleted = 0
JOIN projects p  ON p.id = e.project_id
LEFT JOIN bookings b
       ON b.enquiry_id = e.id
      AND b.isDeleted = 0
      AND b.bookingStatus NOT IN ('CANCELED', 'BOOKING_REJECTED')
WHERE e.isDeleted = 0
  AND e.isActive = 1
  AND e.source = 'REFERRAL'
ORDER BY e.createdOn DESC;
```

### 11.2 Bookings extract

```sql
SELECT
    b.id                    AS booking_id,
    b.crmId                 AS booking_crm_id,
    b.bookingDate,
    b.createdOn             AS booking_created_on,
    b.bookingStatus,
    b.source                AS booking_source,
    b.unitNumber,
    b.agreementValue,
    b.user_id               AS booking_user_id,
    b.enquiry_id,
    e.source                AS enquiry_source,
    e.referralSource,
    e.createdOn             AS enquiry_created_on,
    e.user_id               AS enquiry_user_id,
    e.lead_id,
    e.project_id,
    p.projectName,
    l.name                  AS lead_name,
    l.hashId                AS lead_hash_id,
    l.mobileNumber,
    l.email,
    b.property_id
FROM bookings b
LEFT JOIN enquires e  ON e.id = b.enquiry_id AND e.isDeleted = 0
LEFT JOIN leads l     ON l.id = e.lead_id AND l.isDeleted = 0
LEFT JOIN projects p  ON p.id = e.project_id
WHERE b.isDeleted = 0
  AND b.bookingStatus NOT IN ('CANCELED', 'BOOKING_REJECTED')
ORDER BY b.bookingDate DESC;
```

---

## 12. Contact / ownership

- **Data model source:** `loyalie_entities` (shared JPA entities)  
- **Document:** Step 1 dataset guide for referral bypass analysis  
- **Next steps (not in this pack):** identity matching, bypass classification, same vs cross-project reporting  

If column names in the shared files differ slightly (casing/export tool), map them using the **field dictionaries** in §4 and §5; semantic meaning is authoritative over exact export labels.
