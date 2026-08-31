# 🎯 Automatic File Detection - आसान गाइड (Hindi)

## 🚀 अब कोड में changes करने की जरूरत नहीं!

आपका CA Foundation Quiz Master Bot अब **automatic detection** system के साथ आ गया है। अब आप बस file upload करो, और bot खुद समझ जाएगा कि वो file किस subject की है!

---

## 🎯 कैसे काम करता है?

Bot आपकी **file के नाम** को देखकर automatically decide करता है कि वो file:
- 📈 Economics में जानी चाहिए
- 📊 Accounts में जानी चाहिए  
- 🧮 Quantitative Aptitude में जानी चाहिए

---

## 📝 File का नाम कैसे रखें?

### 1️⃣ Economics Files के लिए:

File name में ये words होने चाहिए:
```
economics, eco, business, chapter, ch, jan, feb, mar, apr, may, 
jun, jul, aug, sep, oct, nov, dec, mtp, pyq, exam
```

**✅ सही Examples:**
- `Chapter1.txt` ✅
- `Chapter2.txt` ✅
- `jan26.txt` ✅
- `may25.txt` ✅
- `MTP1(sept26).txt` ✅
- `economics_quiz.txt` ✅

---

### 2️⃣ Accounts Files के लिए:

File name में ये words होने चाहिए:
```
account, accounts, acc, tf, true, false, quiz, ledger, journal
```

**✅ सही Examples:**
- `accounts_tf.txt` ✅
- `accounts_tf_last_20_attempts.txt` ✅
- `acc_practice.txt` ✅
- `accounting_quiz.txt` ✅

---

### 3️⃣ Quantitative Aptitude Files के लिए:

File name में ये words होने चाहिए:
```
maths, math, statistics, stats, quant, qa, aptitude, numerical
```

**✅ सही Examples:**
- `maths_chapter1.txt` ✅
- `statistics_basics.txt` ✅
- `qa_practice.txt` ✅
- `quantitative_aptitude.txt` ✅

---

## 🎯 Step-by-Step इस्तेमाल कैसे करें?

### Step 1: File का नाम सही रखो

**Economics के लिए:**
```
Chapter1.txt
jan26.txt
economics_pyq.txt
```

**Accounts के लिए:**
```
accounts_tf.txt
acc_module1.txt
accounting_quiz.txt
```

**Maths के लिए:**
```
maths_chapter1.txt
statistics_quiz.txt
qa_practice.txt
```

---

### Step 2: `data/` Folder में Upload करो

बस अपनी file को `data/` folder में डाल दो:

```
data/
├── Chapter1.txt              → ✅ Economics में जाएगी
├── accounts_tf.txt           → ✅ Accounts में जाएगी
├── maths_practice.txt        → ✅ Quant में जाएगी
├── jan26.txt                 → ✅ Economics में जाएगी
└── statistics_quiz.txt       → ✅ Quant में जाएगी
```

---

### Step 3: Bot को Reload करो (Optional)

अगर bot चल रहा है तो:
- `/reload` command भेजो
- या bot को restart करो

**बस! हो गया! ✅**

---

## 🎉 फायदे

### पहले (Before):
```
❌ हर नई file के लिए code में changes करने पड़ते थे
❌ Manual categorization की जरूरत थी
❌ Developer को हर बार बताना पड़ता था
```

### अब (After):
```
✅ File का नाम सही रखो
✅ Upload करो
✅ Automatically सही category में चली जाएगी!
```

---

## 📊 Bot Start होने पर Logs

जब bot start होता है, तो आपको ये दिखेगा:

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

## 🎯 Mock Test में कैसे दिखेगा?

### `/mocktest` Command चलाने पर:

**📈 Business Economics Button:**
- सभी Economics files दिखेंगी
- Chapters, PYQs, exam papers सब यहाँ होंगे

**📊 Accounts T/F Button:**
- सभी Accounts files दिखेंगी
- TF questions, quiz सब यहाँ होंगे

**🧮 Quantitative Aptitude Button:**
- सभी Maths/Stats files दिखेंगी
- अगर कोई file नहीं है तो "Coming Soon" दिखेगा

---

## 🚨 Problem Ho Toh?

### Problem 1: File सही category में नहीं दिख रही

**Solution:** File के नाम में सही keyword डालो

```
❌ myfile.txt → Economics में जाएगी (default)
✅ myfile_maths.txt → Quant में जाएगी
```

---

### Problem 2: Quant button पे "Coming Soon" दिख रहा है

**Solution:** कोई भी Maths/Stats file upload नहीं की है। File name में `maths`, `stats` या `quant` डालो।

```
✅ maths_chapter1.txt upload करो
✅ statistics_practice.txt upload करो
```

---

### Problem 3: File गलत category में चली गई

**Solution:** File का नाम change करो

```
❌ accounts_maths.txt → Accounts में जाएगी
   (पहले accounts keyword match हो गया)

✅ maths_accounts_topic.txt → Quant में जाएगी
   (पहले maths keyword match होगा)
```

---

## 📝 Quick Reference Table

| File Name | Detected As | Reason |
|-----------|-------------|--------|
| `Chapter1.txt` | 📈 Economics | "chapter" keyword |
| `jan26.txt` | 📈 Economics | "jan" month keyword |
| `accounts_tf.txt` | 📊 Accounts | "accounts" keyword |
| `maths_ch1.txt` | 🧮 Quant | "maths" keyword |
| `MTP1(sept26).txt` | 📈 Economics | "sept" month + "mtp" |
| `acc_practice.txt` | 📊 Accounts | "acc" keyword |
| `statistics_quiz.txt` | 🧮 Quant | "statistics" keyword |
| `random.txt` | 📈 Economics | No match (default) |

---

## ✅ सही तरीका

### Economics Files:
```
✅ Chapter1.txt
✅ Chapter2.txt
✅ jan26.txt
✅ may25.txt
✅ MTP1(sept26).txt
✅ economics_pyq_2024.txt
```

### Accounts Files:
```
✅ accounts_tf.txt
✅ accounts_module1.txt
✅ acc_practice.txt
✅ accounting_tf.txt
```

### Maths Files:
```
✅ maths_chapter1.txt
✅ statistics_basics.txt
✅ qa_practice.txt
✅ quant_aptitude.txt
```

---

## 🎊 Summary

**अब बहुत आसान है!**

1. ✅ File का नाम सही रखो (keyword डालो)
2. ✅ `data/` folder में upload करो
3. ✅ `/reload` भेजो या restart करो
4. ✅ **Automatically सही जगह दिखेगी!**

---

## 💡 Pro Tips

1. **Chapter files:** Name में "Chapter" या "Ch" जरूर रखो
2. **Month-wise papers:** Month name डालो (jan, feb, mar, etc.)
3. **Accounts:** "accounts" या "tf" या "acc" डालो
4. **Maths:** "maths" या "stats" या "qa" डालो

---

## 📞 Help Chahiye?

अगर कोई problem है या custom keywords add करने हैं:

📩 Telegram: [@Cagourav_18](https://t.me/Cagourav_18)

---

**🎯 अब कभी code में changes नहीं करने पड़ेंगे! Bas file upload karo aur enjoy karo! 🚀**
