# 🎯 Automatic Subject Detection System

## Overview

Your CA Foundation Quiz Master Bot now features an **intelligent auto-detection system** that automatically categorizes question files into the correct subject without any code changes!

---

## ✨ How It Works

When you upload a new file to the `data/` folder, the bot automatically detects which subject category it belongs to based on the **filename**.

### 🔍 Detection Rules

The system checks the filename for specific keywords and assigns it to the appropriate category:

---

## 📊 Subject Categories

### 1. **📈 Business Economics**

Files automatically go to Economics if the filename contains:

```
economics, economy, eco, business, chapter, ch, demand, supply, 
production, market, income, trade, mtp, rtp, pyq, exam
```

**Month names also trigger Economics:**
```
jan, feb, mar, apr, may, jun, jul, aug, sep, oct, nov, dec
```

**Examples:**
- ✅ `Chapter1.txt` → Economics
- ✅ `Chapter2.txt` → Economics  
- ✅ `jan26.txt` → Economics
- ✅ `may25.txt` → Economics
- ✅ `MTP1(sept26).txt` → Economics
- ✅ `economics_pyq.txt` → Economics
- ✅ `business_quiz.txt` → Economics

---

### 2. **📊 Accounts (True/False)**

Files automatically go to Accounts if the filename contains:

```
account, accounts, accounting, acc, tf, true, false, truefalse, 
true_false, quiz, ledger, journal, balance
```

**Examples:**
- ✅ `accounts_tf.txt` → Accounts
- ✅ `accounts_tf_last_20_attempts.txt` → Accounts
- ✅ `accounting_quiz.txt` → Accounts
- ✅ `acc_practice.txt` → Accounts
- ✅ `journal_tf.txt` → Accounts

---

### 3. **🧮 Quantitative Aptitude**

Files automatically go to Quant if the filename contains:

```
maths, math, mathematics, stats, statistics, quantitative, 
quant, qa, aptitude, numerical, calculation
```

**Examples:**
- ✅ `maths_chapter1.txt` → Quant
- ✅ `statistics_basics.txt` → Quant
- ✅ `quantitative_aptitude.txt` → Quant
- ✅ `qa_practice.txt` → Quant
- ✅ `numerical_ability.txt` → Quant

---

## 🚀 How to Use

### Step 1: Name Your File Correctly

Just include the subject keyword in your filename:

```bash
# For Economics:
Chapter1.txt
jan26_economics.txt
business_pyq.txt

# For Accounts:
accounts_module1.txt
accounting_tf.txt
acc_quiz.txt

# For Quantitative Aptitude:
maths_chapter1.txt
statistics_practice.txt
qa_questions.txt
```

### Step 2: Upload to Data Folder

Simply place your `.txt` or `.json` file in the `data/` folder:

```
data/
├── Chapter1.txt              → Auto-detected as Economics
├── accounts_tf.txt           → Auto-detected as Accounts
├── maths_practice.txt        → Auto-detected as Quant
├── jan26.txt                 → Auto-detected as Economics
└── statistics_quiz.txt       → Auto-detected as Quant
```

### Step 3: Reload (Optional)

If bot is running, use `/reload` command or restart the bot. Done! ✅

---

## 📋 File Format

Questions should follow this format in `.txt` files:

```
Q: What is 2 + 2?
A) 3
B) 4
C) 5
D) 6
Ans: B
Exp: Basic addition: 2 + 2 = 4

---

Q: Capital of India?
A) Mumbai
B) Delhi
C) Kolkata
D) Chennai
Ans: B
Exp: New Delhi is the capital of India.
```

**Separators:** Use `---` or `===` between questions

---

## 🔄 Default Behavior

If a filename doesn't match any keywords, it **defaults to Economics**.

**Example:**
- `random_questions.txt` → Economics (default)
- `test123.txt` → Economics (default)

---

## 📊 Bot Startup Logs

When the bot starts, you'll see auto-detection in action:

```
✅ Total unique questions loaded: 450
📈 Economics: Chapter1.txt
📈 Economics: jan26.txt
📈 Economics: may25.txt
📊 Accounts: accounts_tf.txt
📊 Accounts: accounts_tf_last_20_attempts.txt
🧮 Quantitative: maths_chapter1.txt
🧮 Quantitative: statistics_basics.txt

📈 Economics files: 3
📊 Accounts files: 2
🧮 Quant files: 2
```

---

## 🎯 Mock Test Integration

The bot automatically shows files under the correct subject button:

### Business Economics Button
- Shows all Economics files (chapters + PYQs)
- Includes files with: `chapter`, `jan`, `may`, `mtp`, `economics`, etc.

### Accounts T/F Button
- Shows all Accounts files
- Includes files with: `accounts`, `tf`, `acc`, etc.

### Quantitative Aptitude Button
- Shows all Quant files
- Includes files with: `maths`, `stats`, `qa`, etc.
- If no files found, shows "Coming Soon"

---

## ✅ Benefits

1. **🎯 Zero Code Changes** - Just upload files with proper names
2. **⚡ Instant Recognition** - Automatic categorization
3. **🔄 Flexible** - Works with .txt and .json files
4. **📊 Smart Sorting** - Files appear in the right category
5. **🚀 Easy Maintenance** - No hardcoded file lists

---

## 🛠️ Advanced: Custom Keywords

Want to add more keywords? Edit `questions_loader.py`:

```python
# Around line 32-50
ECONOMICS_KEYWORDS = [
    "economics", "economy", "eco", "business", "chapter", "ch",
    "demand", "supply", "production", "market", "income", "trade",
    # Add your custom keywords here:
    "custom_eco_keyword",
]

ACCOUNTS_KEYWORDS = [
    "account", "accounts", "accounting", "acc", "tf", "true", "false",
    # Add your custom keywords here:
    "custom_acc_keyword",
]

QUANT_KEYWORDS = [
    "maths", "math", "mathematics", "stats", "statistics", "quantitative",
    # Add your custom keywords here:
    "custom_quant_keyword",
]
```

---

## 📝 Examples by Subject

### Economics Files ✅
```
✅ Chapter1.txt
✅ Chapter2.txt
✅ Chapter3.txt
✅ jan26.txt
✅ may25.txt
✅ sept24.txt
✅ MTP1(sept26).txt
✅ economics_practice.txt
✅ business_quiz.txt
✅ pyq_2024.txt
```

### Accounts Files ✅
```
✅ accounts_tf.txt
✅ accounts_tf_last_20_attempts.txt
✅ accounting_module1.txt
✅ acc_practice.txt
✅ ledger_quiz.txt
✅ journal_tf.txt
```

### Quantitative Files ✅
```
✅ maths_chapter1.txt
✅ statistics_basics.txt
✅ quantitative_aptitude.txt
✅ qa_practice.txt
✅ numerical_ability.txt
✅ math_quiz.txt
```

---

## 🚨 Troubleshooting

### Problem: File not showing in correct category

**Solution:** Check the filename contains a keyword from the list above.

**Example:**
```
❌ myfile.txt → Goes to Economics (default)
✅ myfile_maths.txt → Goes to Quantitative
```

### Problem: Quant button shows "Coming Soon"

**Solution:** No files detected with Quant keywords. Upload a file with `maths`, `stats`, or `quant` in the name.

### Problem: File showing in wrong category

**Solution:** Rename the file to include the correct keyword.

**Example:**
```
❌ accounts_maths.txt → Goes to Accounts (accounts keyword matched first)
✅ maths_accounts_topic.txt → Goes to Quant (maths checked first)
```

---

## 🎉 Summary

**No more code changes needed!** Just:

1. ✅ Name your file with subject keywords
2. ✅ Upload to `data/` folder
3. ✅ Reload or restart bot
4. ✅ File automatically appears in correct category!

---

## 📞 Need Help?

If you need to add custom keywords or have special categorization needs, contact the developer:

📩 Telegram: [@Cagourav_18](https://t.me/Cagourav_18)

---

**🎯 Smart. Simple. Automatic. No code changes ever again!**
