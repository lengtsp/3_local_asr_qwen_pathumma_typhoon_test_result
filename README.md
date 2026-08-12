# Local Thai ASR Comparison

Before adding a **speech-to-text** feature to an internal Local AI system, three Thai ASR models were evaluated on the same audio clip and the same human-checked reference. The comparison covers transcription accuracy and practical GPU startup time.

## 1. Scope

### Models compared

1. [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
2. [nectec/Pathumma-whisper-th-large-v3](https://huggingface.co/nectec/Pathumma-whisper-th-large-v3)
3. [typhoon-ai/typhoon-asr-realtime](https://huggingface.co/typhoon-ai/typhoon-asr-realtime)

### Test input

| Item | Value |
| --- | --- |
| Source video | [YouTube: j6bYGueQ8Ro](https://www.youtube.com/watch?v=j6bYGueQ8Ro) |
| Evaluated audio | `test1.mp3`, 77.5 seconds |
| Content | Thai news with proper names, abbreviations, and many spoken numbers |
| Gold reference | Human-checked transcript; 897 characters after NFC normalization and whitespace removal |
| Hardware | NVIDIA RTX PRO 6000 Blackwell Workstation Edition / CUDA |

The original audio is not published because it is a local/internal file. This repository contains only the report and a credential-free inference notebook; it has no absolute local paths.

> **Scope limitation:** these measurements use one audio sample. They are useful for selecting an initial implementation for this use case, not for claiming a universal ranking across every Thai ASR domain.

## 2. Transcription accuracy

| Model | Strict CER | Content CER |
| --- | ---: | ---: |
| Qwen3-ASR-1.7B | 21.1817% | 3.8724% |
| Pathumma | **8.5842%** | 2.8474% |
| Typhoon | 18.3946% | **0.3417%** |

Score definitions:

- **Strict CER** requires every character to match the reference, including number representation (`397` versus `สามร้อยเก้าสิบเจ็ด`), abbreviations, punctuation, and the closing tag.
- **Content CER** measures spoken content. The same clip-specific normalization is applied to every model: Thai number words are converted to the corresponding Arabic values in the reference, thousands separators are removed, `ํา` and `ำ` are treated as equivalent, and the closing tag `7HD TV เพื่อคุณ` is excluded.

## 3. CUDA cold model start time

| Model | Cold model load | Decode | Total cold start |
| --- | ---: | ---: | ---: |
| Qwen3-ASR-1.7B | 8.19 s | 13.28 s | 21.47 s |
| Pathumma | 6.36 s | 14.70 s | 21.06 s |
| Typhoon | **4.68 s** | **0.93 s** | **5.61 s** |

All models use the same timing definition: a new Python process, no target model already resident in GPU memory, and locally cached weights only—no network download. The measurement includes `model initialization on GPU + transcription`; it excludes Python import, audio-file reading/resampling, package installation, and weight download.

> **Decode** is the time after the model is ready on the GPU to turn a prepared audio waveform into text. It includes feature extraction and ASR inference/generation. Pathumma uses four 25-second Whisper chunks; Qwen and Typhoon receive the complete audio file.

## 4. Decision summary

For this sample, Typhoon is the preferred Local AI option when the goal is accurate Thai news content with low startup and inference time: **0.3417% Content CER** and **5.61 seconds total cold start**.

Typhoon's higher Strict CER (**18.3946%**) does not necessarily mean that it misheard the content. In this sample, it returns spoken numbers as **Thai number words**, for example `สามร้อยเก้าสิบเจ็ด` rather than `397`—not Thai digits `๓๙๗`—and it omits the closing tag. After the number-word representation is normalized to the Arabic form used by the reference, its Content CER is 0.3417%.

Recommended implementation approach:

1. Use Typhoon as the primary ASR engine for this use case and apply context-aware numeric post-processing.
2. Preserve the raw transcript before normalization for auditability.
3. If raw output must follow the Arabic-number reference format without normalization, Pathumma achieved the better Strict CER on this sample.
4. Before production rollout, evaluate a larger holdout set covering multiple domains, proper names, numbers, and audio-quality conditions.

## 5. Gold reference and model outputs

The Thai text below is intentionally kept unchanged because it is the gold reference and the actual ASR output. `<mark>…</mark> 🟥` marks a likely lexical or spelling error; `🔷…🔷` marks a number-format or abbreviation difference counted by Strict CER but not necessarily a semantic error.

<details>
<summary>Show the gold reference and the complete output of all three models with their scores</summary>

### Gold reference

> ศูนย์ต่อต้านการฉ้อโกงออนไลน์นะคะ ส่งข้อมูลให้ตำรวจตามจับกุมวัยรุ่นค่ะ ที่มีการถอนเงินหน้าธนาคาร เพื่อส่งไปให้บัญชีม้านะคะ ขณะที่ภาพรวมตลอดทั้งสัปดาห์ มีคนถูกหลอกโอนเงิน รวมความเสียหายกว่า 397 ล้านบาท นี่เป็นหนึ่งในคดีที่ศูนย์ต่อต้านการฉ้อโกงออนไลน์ ประสานตำรวจในพื้นที่ สภ.เชียงดาว จังหวัดเชียงใหม่ จับกุมวัยรุ่นชายอายุ 17 และ 19 ปี หลังรับงานกดเงินสดถอนเงินให้กับแก๊งสแกมเมอร์ จากธนาคารแห่งหนึ่ง เบื้องต้นพบของกลางเงินสด 150,000 บาท สมุดบัญชีธนาคาร บัตร ATM และโทรศัพท์มือถือ 2 เครื่อง สอบถามผู้ต้องหารับว่า ได้รับงานกดถอนเงินให้กับชายวัยรุ่นอีกคนอายุ 19 ปี ซึ่งก่อนหน้านี้ก็เพิ่งไปถอนเงินสด 100,000 บาท จากพื้นที่ สภ.นาหวาย ให้ไป แลกกับค่าตอบแทน 5,000 บาท ขณะที่ภาพรวมมีการจับกุมผู้ต้องหารวม 11 คดี ยึดของกลางเงินสดได้รวมกว่า 5,400,000 บาท ขณะที่ภาพรวมวันที่ 5 ถึง 11 เมษายน ที่ผ่านมา พบว่ามีผู้เสียหายแจ้งความผ่านระบบออนไลน์รวมกว่า 7,300 คดี ความเสียหายรวมกว่า 397 ล้านบาท ในจำนวนนี้เป็นคดีหลอกลงทุน สร้างความเสียหายมากที่สุดรวมกว่า 213 ล้านบาท
>
> 7HD TV เพื่อคุณ

### Pathumma — Strict CER 8.5842%, Content CER 2.8474%

> ศูนย์ต่อต้านการฉ้อโกงออนไลน์นะคะส่งข้อมูลให้ตำรวจตามจับ<mark>กลุ่ม</mark> 🟥วัยรุ่นค่ะที่มีการถอนเงินหน้าธนาคารเพื่อส่งไปให้บัญชีม้านะคะขณะที่ภาพรวมตลอดทั้งสัปดาห์มีคนถูกหลอกโอนเงินรวมความเสียหายกว่า🔷สามร้อยเก้าสิบเจ็ด🔷ล้านบาทนี่เป็นหนึ่งในคดีที่ศูนย์ต่อต้านการฉ้อโกงออนไลน์ประสานตำรวจในพื้นที่<mark>สพ</mark> 🟥เชียงดาวจังหวัดเชียงใหม่จับ<mark>กลุ่ม</mark> 🟥วัยรุ่นชายอายุ🔷สิบเจ็ด🔷และ🔷สิบเก้า🔷ปีหลังรับงานกดเงินสดถอนเงินให้กับแก๊งสแกมเมอร์จากธนาคารแห่งหนึ่งเบื้องต้นพบของกลางเงินสด150,000บาทสมุดบัญชีธนาคารบัตร🔷เอทีเอ็ม🔷และโทรศัพท์มือถือ2เครื่องสอบถามผู้ต้องหารับว่าได้รับงานกดถอนเงินให้กับชายวัยรุ่นอีกคนอายุ19ปีซึ่งก่อนหน้านี้ก็เพิ่งไปถอนเงินสด100,000บาทจากพื้นที่<mark>สพนาวาย</mark> 🟥ให้ไป<mark>แล้ว</mark> 🟥กับค่าตอบแทน5,000บาทขณะที่ภาพรวมมีการ<mark>กลุ่ม</mark> 🟥ผู้ต้องหารวม11คดี<mark>ยืด</mark> 🟥ของกลางเงินสดได้รวมกว่า🔷5ล้าน4แสน🔷บาทขณะที่ภาพรวมวันที่5ถึง11เมษายนที่ผ่านมาพบว่ามีผู้เสียหายแจ้งความผ่านระบบออนไลน์รวมกว่า7,300คดีความเสียหายรวมกว่า397ล้านบาทในจำนวนนี้เป็นคดีหลอกลงทุนสร้างความเสียหายมากที่สุดรวมกว่า213ล้านบาท<mark>โอ้โห</mark> 🟥

### Qwen3-ASR-1.7B — Strict CER 21.1817%, Content CER 3.8724%

> ศูนย์ต่อต้านการ<mark>ช้อกง</mark> 🟥ออนไลน์นะคะส่งข้อมูลให้ตำรวจตามจับ<mark>กลุ่ม</mark> 🟥วัยรุ่นค่ะที่มีการถอนเงินหน้าธนาคารเพื่อส่งไปให้บัญชีม้านะคะขณะที่ภาพรวมตลอดทั้งสัปดาห์มีคนถูกหลอกโอนเงินรวมความเสียหายกว่า🔷สามร้อยเก้าสิบเจ็ด🔷ล้านบาทนี่เป็นหนึ่งในคดีที่ศูนย์ต่อต้านการ<mark>ช้อกง</mark> 🟥ออนไลน์ประสานตำรวจในพื้นที่<mark>สพ</mark> 🟥เชียงดาวจังหวัดเชียงใหม่จับ<mark>กลุ่ม</mark> 🟥วัยรุ่นชายอายุ🔷สิบเจ็ด🔷และ🔷สิบเก้า🔷ปี<mark>ลัง</mark> 🟥รับงาน<mark>โกรธ</mark> 🟥เงินสดถอนเงินให้กับแก๊งสแกมเมอร์จากธนาคารแห่งหนึ่งเบื้องต้นพบของกลางเงินสด🔷หนึ่งแสนห้าหมื่น🔷บาทสมุดบัญชีธนาคารบัตร🔷เอทีเอ็ม🔷และโทรศัพท์มือถือ🔷สอง🔷เครื่องสอบถามผู้ต้องหารับว่าได้รับงาน<mark>โกรธ</mark> 🟥ถอนเงินให้กับชายวัยรุ่นอีกคนอายุ🔷สิบเก้า🔷ปีซึ่งก่อนหน้านี้ก็<mark>พึ่ง</mark> 🟥ไปถอนเงินสด🔷หนึ่งแสนบาทจากพื้นที่<mark>สพนวาย</mark> 🟥ให้ไปแลกกับค่าตอบแทน🔷ห้าพัน🔷บาทขณะที่ภาพรวมมีการจับ<mark>กลุ่ม</mark> 🟥ผู้ต้องหารวม🔷สิบเอ็ด🔷คดียึดของกลางเงินสดได้รวมกว่า🔷ห้าล้านสี่แสน🔷บาทขณะที่ภาพรวมวันที่🔷ห้า🔷ถึง🔷สิบเอ็ด🔷เมษายนที่ผ่านมาพบว่ามีผู้เสียหายแจ้งความผ่านระบบออนไลน์รวมกว่า🔷เจ็ดพันสามร้อย🔷คดีความเสียหายรวมกว่า🔷สามร้อยเก้าสิบเจ็ด🔷ล้านบาทในจำนวนนี้เป็นคดีหลอกลงทุนสร้างความเสียหายมากที่สุดรวมกว่า🔷สองร้อยสิบสาม🔷ล้านบาท

### Typhoon — Strict CER 18.3946%, Content CER 0.3417%

> ศูนย์ต่อต้านการฉ้อโกงออนไลน์นะคะส่งข้อมูลให้ตำรวจตามจับกุมวัยรุ่นค่ะที่มีการถอนเงินหน้าธนาคารเพื่อส่งไปให้บัญชีม้านะคะ ขณะที่ภาพรวมตลอดทั้งสัปดาห์มีคนถูกหลอกโอนเงินรวมความเสียหายกว่า🔷สามร้อยเก้าสิบเจ็ด🔷ล้านบาท นี่เป็นหนึ่งในคดีที่ศูนย์ต่อต้านการฉ้อโกงออนไลน์ประสานตำรวจในพื้นที่ <mark>สภ</mark> 🟥เชียงดาว จังหวัดเชียงใหม่ จับกุมวัยรุ่นชายอายุ🔷สิบเจ็ด🔷และ🔷สิบเก้า🔷ปี หลังรับงานกดเงินสดถอนเงินให้กับแก๊งสแกมเมอร์จากธนาคารแห่งหนึ่ง เบื้องต้นพบของกลางเงินสด 🔷หนึ่งแสนห้าหมื่น🔷บาท สมุดบัญชีธนาคาร บัตร ATM และโทรศัพท์มือถือ🔷สอง🔷เครื่อง สอบถามผู้ต้องหารับว่าได้รับงานกด ถอนเงินให้กับชายวัยรุ่นอีกคนอายุ🔷สิบเก้า🔷ปี ซึ่งก่อนหน้านี้ก็เพิ่งไปถอนเงินสด🔷หนึ่งแสน🔷บาทจากพื้นที่ สภ.นาหวายให้ไป <mark>เลิก</mark> 🟥กับค่าตอบแทน🔷ห้าพัน🔷บาท ขณะที่ภาพรวมมีการจับกุมผู้ต้องหารวม🔷สิบเอ็ด🔷คดียึดของกลางเงินสดได้รวมกว่า🔷ห้าล้านสี่แสน🔷บาท ขณะที่ภาพรวมวันที่🔷ห้า🔷ถึง🔷สิบเอ็ด🔷เมษายนที่ผ่านมา พบว่ามีผู้เสียหายแจ้งความผ่านระบบออนไลน์รวมกว่า🔷เจ็ดพันสามร้อย🔷คดี ความเสียหายรวมกว่าสามร้อยเก้าสิบเจ็ดล้านบาท ในจำนวนนี้เป็นคดีหลอกลงทุนสร้างความเสียหายมากที่สุดรวมกว่า🔷สองร้อยสิบสาม🔷ล้านบาท

</details>

## 6. Published files

- [typhoon_asr_inference_example.ipynb](typhoon_asr_inference_example.ipynb) — a Typhoon CUDA example using the placeholder path `sample_audio.mp3`, executed locally before publication with its example output embedded.
- [Qwen3-ASR-1.7B model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
- [Pathumma model card](https://huggingface.co/nectec/Pathumma-whisper-th-large-v3)
- [Typhoon model card](https://huggingface.co/typhoon-ai/typhoon-asr-realtime)

No model weights, private audio, raw transcripts, raw JSON results, credentials, or absolute local paths are published in this repository.
