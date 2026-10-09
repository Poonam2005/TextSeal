# TextSeal - Demo and Viva Guide

## Five-minute demo sequence

1. Start the Django server and open `http://127.0.0.1:8000`.
2. Explain the problem: AI text can be copied or changed, so appearance alone is not proof of origin or integrity.
3. Paste a short paragraph in **Watermark & register**. Enter `Demo LLM` as model information and a meaningful source note. Select **Seal text**.
4. Point out the text ID, SHA-256 value, local-ledger reference, and invisible output. Explain that the zero-width characters do not alter what a reader sees.
5. Open **Verify provenance**. The sealed text is already available there. Select **Verify text** and show **Authentic & unchanged**.
6. Change one visible word but keep the invisible watermark. Verify again and show **Modified / tampered**.
7. Paste an unrelated paragraph and show **Not registered**.
8. Open **Review ledger**. Explain the number of records, verification events, and successful ledger integrity check.
9. Close with the limitation: the local ledger demonstrates immutable-chain concepts; a real Polygon/Ethereum transaction requires a final smart contract and credentials.
10. Open the registered receipt link and show its selected proof fields. Run the robustness evaluation and explain why whitespace normalization passes, a punctuation edit is modified, and watermark removal becomes unregistered.
11. Optionally demonstrate a text-based PDF or DOCX upload. Scanned PDFs are not OCR-processed.

## Strong viva answers

### Why not only use an AI detector?

AI detectors estimate writing patterns. TextSeal verifies a particular registered item using a signed watermark, cryptographic hash, and provenance record. It does not claim that any text that “looks like AI” is authentic.

### What is the role of SHA-256?

SHA-256 creates a fixed-size fingerprint of the canonical visible text. A visible modification produces a different digest, so the system can detect tampering.

### What is canonicalization and why is it necessary?

The same text may have different newlines or trailing whitespace. Canonicalization creates one consistent representation before hashing, reducing false mismatches caused by ordinary formatting differences.

### How is the watermark hidden?

The application converts a payload containing the version, UUID, and HMAC signature into zero-width Unicode characters. The reader sees the original text, while TextSeal can extract the hidden payload later.

### Why use HMAC?

HMAC signs the text ID with a server-side secret. An attacker cannot create a valid TextSeal token without that secret. The secret must not be included in frontend JavaScript or committed to Git.

### Is the current ledger a real blockchain?

No. It is a local tamper-evident hash chain for a controlled academic prototype. The PRD leaves the contract ABI and on-chain storage policy open. The project clearly labels the current reference as `local-ledger`, so it does not overclaim a public-chain transaction.

### What happens if the ledger is inconsistent?

The system returns **Verification unavailable**. It does not return an authentic result if the supporting provenance ledger cannot be trusted.

### What are the limitations?

Zero-width watermarks can be removed by sanitization and may not survive paraphrasing. A provenance record indicates a registration event; it does not alone prove every real-world authorship claim.

## Test cases to show evaluators

| Test | Input | Expected result |
| --- | --- | --- |
| Exact verification | Registered sealed text | Authentic & unchanged |
| One-word edit | Same sealed text with one visible word changed | Modified / tampered |
| Unregistered input | Different plain text | Not registered |
| Token alteration | Alter/remove hidden payload | Watermark invalid or Not registered |
| Ledger integrity failure | Alter a ledger block only in a controlled test database | Verification unavailable |
| File input | Valid UTF-8 `.txt` file | Same outcome as pasted text |
| DOCX input | DOCX with readable paragraphs | Extracted text follows the same seal/verify workflow |
| PDF input | Text-based PDF | Extracted text follows the same seal/verify workflow; scanned-image OCR is unsupported |
| Robustness evaluation | Registered sealed text | Four expected outcomes are compared without adding verification audit events |
| Receipt | Existing text ID | Shows selected provenance fields without original text or private notes |

## Report chapter outline

1. Introduction and motivation
2. Literature survey: AI text watermarking, provenance, content integrity
3. Problem statement, objectives, and scope
4. Requirement analysis and system design
5. Methodology: canonicalization, HMAC watermark, SHA-256, local ledger
6. Implementation and module description
7. Test cases, screenshots, and results
8. Limitations, future scope, conclusion, and references

Never describe the local ledger as a deployed Polygon/Ethereum transaction in the report or presentation. Accurate engineering claims will strengthen the project evaluation.
