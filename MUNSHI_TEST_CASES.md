# Munshi — Manual Test Cases
**How to use:** Send each message from a second phone to the WhatsApp number linked to Munshi.
After each message, check the response Munshi sends back AND verify the SQLite state:
```
Invoke-RestMethod -Uri "http://localhost:8000/tasks/{your_phone_lid}" | ConvertTo-Json -Depth 5
```

---

## CATEGORY 1 — FOLLOW_UP (Pending payments / receivables)

These should all create a task with `intent_type: FOLLOW_UP` and extract the contact + amount.

| # | Message | Expected intent | Expected entities |
|---|---|---|---|
| F1 | `Sharma ji ka payment 50k pending hai` | FOLLOW_UP | name: Sharma ji, amount: 50000 |
| F2 | `Ravi ne 25000 dena hai` | FOLLOW_UP | name: Ravi, amount: 25000 |
| F3 | `Kapoor ji ka 1 lakh baaki hai 3 mahine se` | FOLLOW_UP | name: Kapoor ji, amount: 100000 |
| F4 | `Meena ka invoice clear nahi hua` | FOLLOW_UP | name: Meena |
| F5 | `bhai suresh ne abhi tak paise nahi bheje` | FOLLOW_UP | name: Suresh |
| F6 | `ABC Corp owes me 75000 from last month` | FOLLOW_UP | name: ABC Corp, amount: 75000 |
| F7 | `Deepak bhai 2 lakh dena tha wo kab dega` | FOLLOW_UP | name: Deepak, amount: 200000 |
| F8 | `Priya ka 500 rupaye wala kaam pending hai` | FOLLOW_UP | name: Priya, amount: 500 |

**Edge cases:**
| # | Message | What to watch |
|---|---|---|
| F9 | `payment pending` (no name, no amount) | Should still create task, action field should capture it |
| F10 | `Sharma ji aur Ravi dono ka payment pending hai` | Should extract both names |
| F11 | `50k` (just an amount, no context) | UNKNOWN intent, clarifying question |

---

## CATEGORY 2 — TASK (Reminders / to-dos)

These should create a task with `intent_type: TASK`. If a date is mentioned, a reminder should be scheduled.

| # | Message | Expected intent | Expected entities |
|---|---|---|---|
| T1 | `Remind me to call Ravi tomorrow at 10am` | TASK | name: Ravi, date: tomorrow |
| T2 | `Kal subah 9 baje Kapoor ji ko call karna hai` | TASK | name: Kapoor ji, date: tomorrow |
| T3 | `GST filing April 20 tak karni hai` | TASK | date: 2026-04-20 |
| T4 | `Remind me to send proposal to Gupta ji by Friday` | TASK | name: Gupta ji, date: Friday |
| T5 | `Electricity bill 15 tarikh tak bharna hai` | TASK | date: 15th |
| T6 | `Shop license renew karna hai next week` | TASK | date: next week |
| T7 | `Ashok ji ko kal tak quotation bhejna hai` | TASK | name: Ashok ji |
| T8 | `Don't forget to follow up with Neha about the order` | TASK | name: Neha |

**Edge cases:**
| # | Message | What to watch |
|---|---|---|
| T9 | `remind me` (no details) | UNKNOWN, clarifying question |
| T10 | `Kal kuch karna hai` (vague) | TASK created but action will be vague |
| T11 | `Call everyone tomorrow` (no specific name) | TASK, no contact_name extracted |
| T12 | `Remind me every Monday to check inventory` | TASK — recurring not supported in V1, should still create one-time task |

---

## CATEGORY 3 — STATUS_QUERY (What's pending?)

These should return the pending tasks list. No new task created.

| # | Message | Expected response |
|---|---|---|
| S1 | `What's pending today?` | List of pending tasks |
| S2 | `Aaj kya karna hai?` | List in Hindi |
| S3 | `Pending tasks dikhao` | List in Hinglish |
| S4 | `Kya chal raha hai?` | List or empty state |
| S5 | `Show me everything pending` | List |
| S6 | `Kitne kaam baaki hain?` | Count + list |
| S7 | `What did I note about Sharma ji?` | Should show Sharma ji related tasks |

**Edge cases:**
| # | Message | What to watch |
|---|---|---|
| S8 | `What's pending?` when nothing is pending | Empty state: "Abhi koi pending kaam nahi hai!" |
| S9 | `Status` (one word) | Should still classify as STATUS_QUERY |
| S10 | `Sab theek hai?` | Ambiguous — might hit UNKNOWN |

---

## CATEGORY 4 — REPLY_DRAFT (Draft a WhatsApp reply)

These should return a `📝 Draft:` prefixed message. No task created.

| # | Message | Expected response |
|---|---|---|
| R1 | `Draft a reply to Sharma ji about the pending payment` | Draft in English |
| R2 | `Meena ko reply karo ki order delay ho gaya` | Draft in Hinglish |
| R3 | `Write a professional message to Gupta ji about the meeting` | Draft in English |
| R4 | `Ravi ko bol do ki payment mil gayi` | Draft in Hindi/Hinglish |
| R5 | `Draft a reply to ABC Corp saying we need 2 more weeks` | Draft in English |
| R6 | `Pooja ko sorry bol do` | Short draft apology |
| R7 | `Neha ko WhatsApp karo delivery ke baare mein` | Draft about delivery |

**Edge cases:**
| # | Message | What to watch |
|---|---|---|
| R8 | `Draft a reply` (no contact mentioned) | Should still draft, contact_name will be "the contact" |
| R9 | `Reply karo` (no context) | UNKNOWN or REPLY_DRAFT with clarifying question |
| R10 | Send R1, then send `Sharma ji ka payment 50k pending hai` | Second message — does ChromaDB context from first message improve the draft? |

---

## CATEGORY 5 — STORE_INFO (Save contact info / notes)

These should create a task with `intent_type: STORE_INFO` and upsert to ChromaDB.

| # | Message | Expected intent | Expected entities |
|---|---|---|---|
| I1 | `Amit ka number 9876543210 hai` | STORE_INFO | name: Amit |
| I2 | `Save Priya's email priya@example.com` | STORE_INFO | name: Priya |
| I3 | `Sharma ji prefers calls in the morning` | STORE_INFO | name: Sharma ji |
| I4 | `Mohan bhai ka address 45 MG Road Bangalore` | STORE_INFO | name: Mohan |
| I5 | `Note karo: Kapoor ji GST number 29ABCDE1234F1Z5` | STORE_INFO | name: Kapoor ji |
| I6 | `Ravi ne confirm kiya hai order ke liye` | STORE_INFO | name: Ravi |

---

## CATEGORY 6 — LANGUAGE HANDLING

Test that Munshi responds in the same language as the input.

| # | Message | Expected response language |
|---|---|---|
| L1 | `What tasks are pending?` | English |
| L2 | `Aaj kya pending hai?` | Hindi |
| L3 | `Sharma ji ka kaam pending hai yaar` | Hinglish |
| L4 | `Remind me to call Ravi kal subah` | Hinglish (mixed) |
| L5 | `Kya aap mujhe bata sakte hain kya pending hai` | Hindi |

---

## CATEGORY 7 — NATURAL / UNSTRUCTURED MESSAGES

These are the real test — casual, messy, real-world messages.

| # | Message | What to watch |
|---|---|---|
| N1 | `arre yaar Ravi ne abhi tak paise nahi bheje kya karu` | FOLLOW_UP, Ravi extracted |
| N2 | `bhai kal subah Kapoor ji ko call karna mat bhoolna please` | TASK, Kapoor ji extracted |
| N3 | `Meena ko bol do na ki order delay ho gaya sorry bolna` | REPLY_DRAFT, Meena extracted |
| N4 | `sab kuch theek hai? koi kaam baaki hai?` | STATUS_QUERY |
| N5 | `Sharma ji 50k, Ravi 25k, Deepak 1 lakh — sab pending hai` | FOLLOW_UP — multiple contacts, should extract all |
| N6 | `ok` | UNKNOWN — clarifying question |
| N7 | `haan` | UNKNOWN — clarifying question |
| N8 | `👍` (just an emoji) | UNKNOWN — clarifying question |
| N9 | `Bhai kal meeting hai Gupta ji ke saath 3 baje, remind karna` | TASK, Gupta ji, date tomorrow 3pm |
| N10 | `Suresh bhai ne bola tha 2 hafte mein dega, ab 3 hafte ho gaye` | FOLLOW_UP, Suresh extracted |
| N11 | `Priya ka invoice 15 tarikh ko tha, aaj 20 ho gayi` | FOLLOW_UP, Priya, overdue |
| N12 | `Yaar kuch yaad nahi reh raha, sab note kar lo` | UNKNOWN or STATUS_QUERY |

---

## CATEGORY 8 — MEMORY / CONTEXT (ChromaDB)

These test whether Munshi remembers past interactions with a contact.

**Run these in sequence:**

| Step | Message | What to verify |
|---|---|---|
| M1 | `Sharma ji ka payment 50k pending hai` | Task created, Sharma ji stored in ChromaDB |
| M2 | `Sharma ji prefers calls after 6pm` | STORE_INFO, updates Sharma ji context in ChromaDB |
| M3 | `Draft a reply to Sharma ji about the payment` | Draft should reference the 50k payment AND the after-6pm preference |

If M3's draft mentions the payment amount or the calling preference — ChromaDB memory is working.

---

## CATEGORY 9 — VOICE NOTES

These require sending actual voice notes from WhatsApp.

| # | Action | Expected behavior |
|---|---|---|
| V1 | Send a voice note saying "Sharma ji ka payment pending hai" | Transcribed, processed as FOLLOW_UP |
| V2 | Send a voice note in Hindi | Transcribed, Hindi response |
| V3 | Send a voice note in Hinglish | Transcribed, Hinglish response |
| V4 | Send a very short voice note (1 second, just noise) | Graceful failure: "Voice note ki samajh nahi aaya" |

---

## CATEGORY 10 — EDGE CASES & STRESS TESTS

| # | Message | Expected behavior |
|---|---|---|
| E1 | Send 5 messages in rapid succession | All processed, no crashes |
| E2 | Very long message (200+ words) | Processed, entities extracted from first 200 chars |
| E3 | Message with special characters: `Sharma ji @#$% payment!!` | Handled gracefully |
| E4 | Message with numbers in words: `do lakh teen hazaar` | Amount extraction — may or may not work (known limitation) |
| E5 | Completely random: `asdfghjkl` | UNKNOWN, clarifying question |
| E6 | SQL injection attempt: `'; DROP TABLE tasks; --` | Handled safely (parameterized queries in sqlite_client) |
| E7 | Empty message (just spaces) | Handled gracefully, no crash |
| E8 | Message only in numbers: `9876543210` | STORE_INFO or UNKNOWN |
| E9 | Restart uvicorn mid-conversation, then send a message | Should work fine after restart |
| E10 | Send a message, check `/tasks/{phone}` endpoint | Task appears in API response |

---

## How to Check Results After Each Test

**Check tasks created:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/tasks/74195677487350" | ConvertTo-Json -Depth 5
```

**Check health:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health" | ConvertTo-Json
```

**Check WAHA logs for webhook delivery:**
```powershell
docker logs waha-waha-1 --since 60s 2>&1 | Select-Object -Last 20
```

**Check LangSmith traces:**
Go to https://smith.langchain.com → project `munshi-prod` → see every agent call with input/output/latency

---

## What to Report Back

For each test category, note:
1. Did Munshi respond at all?
2. Was the response in the right language?
3. Was the intent correct?
4. Were the entities (name, amount, date) extracted correctly?
5. For TASK — did the task appear in `/tasks/{phone}`?
6. For REPLY_DRAFT — was the draft relevant and natural?
7. Any crashes or error messages in uvicorn terminal?
8. Approximate response time (fast / slow / timeout)?
