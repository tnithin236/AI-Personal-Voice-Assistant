# Vaani - verification checklist

Fill the **Result** column yourself (PASS / FAIL / date) while you test. A feature is only "done" when it has a PASS here.
Always start the test in a **New** conversation. Machine: Windows 11, 24 GB RAM, RTX 3050 (4 GB), `gemma3:4b`.

## A. Environment
| # | Test | Expected | Result |
|---|---|---|---|
| A1 | `python scripts\check_env.py` | all required checks pass | |
| A2 | `python -m unittest discover -s tests -t .` | `OK` | |
| A3 | `ollama run gemma3:4b "hi"` | normal reply | |
| A4 | Start everything, then `python scripts\smoke_test.py` | all PASS (Tamil may SKIP); covers H1, H2 and the confirmation rules through the API | |

## B. Text chat
| # | Test | Expected | Result |
|---|---|---|---|
| B1 | Type "Hello" | reply streams word by word, sidebar dot green | |
| B2 | Hover the reply: copy, speak, regenerate | each works; timing shown | |
| B3 | New / Clear / Chat History open + delete | each works | |
| B4 | Close the tab, reopen, open the chat from history | messages are still there | |

## C. Voice - English
| # | Test | Expected | Result |
|---|---|---|---|
| C1 | Language English, hold mic: "What is the capital of France?" | exact transcript, spoken answer | |
| C2 | Hold **Space** with no text box focused | same as the mic button | |
| C3 | "Speaking..." appears only when audio starts | no early "Speaking" | |
| C4 | Press **Stop speaking** mid-answer | audio stops at once | |
| C5 | Speak a long answer ("tell me about the moon") | voice starts before the text finishes | |

## D. Voice - Tamil
| # | Test | Expected | Result |
|---|---|---|---|
| D1 | Language தமிழ், say a full Tamil sentence | transcript in Tamil script, mostly correct | |
| D2 | Tamil reply is spoken (Tamil service running) | audible Tamil speech | |
| D3 | Stop the Tamil service, ask again | red "text only" banner within ~2 s, text reply still appears | |
| D4 | Language Auto, switch between English and Tamil | each answered in its own language | |
| D5 | Settings -> Tamil voice pitch: compare 1.00 and 1.50 with the Test button | 1.50 sounds clearly more feminine and still understandable; the reply voice follows the setting | |

## E. Memory
| # | Test | Expected | Result |
|---|---|---|---|
| E1 | "Remember that my favourite colour is green" | fact appears on Memory page | |
| E2 | New chat: "What's my favourite colour?" | answers green | |
| E3 | Restart the backend, ask again | still answers green | |
| E4 | Add and delete a memory by hand | both work; deleted fact is not used | |
| E5 | Ask 3 ordinary questions | nothing new is saved | |

## F. Documents
| # | Test | Expected | Result |
|---|---|---|---|
| F1 | Upload a PDF and a TXT | both listed with chunk counts | |
| F2 | Ask something inside the file | correct answer, file named | |
| F3 | Ask something NOT in the file | says it could not find it; invents nothing | |
| F4 | Delete the file, ask F2 again | no longer answered | |
| F5 | Upload a .exe | clear error, nothing stored | |

## G. Tools
| # | Test | Expected | Result |
|---|---|---|---|
| G1 | "What's the time?" | correct local time | |
| G2 | "Calculate 15% of 2480" | 372 | |
| G3 | "Search the web for the latest Python release" | answer based on results | |
| G4 | "Find files named sample_notes" | paths inside your user folder | |
| G5 | "Create a folder called vaani_test" | folder on the Desktop | |
| G6 | "Open notepad", "Open youtube.com", "Open Copilot" | each opens; reply is the tool's own sentence | |
| G7 | "Open Photoshop" (not on the list) | short refusal mentioning data/apps.json | |

## H. Safety
| # | Test | Expected | Result |
|---|---|---|---|
| H1 | "Delete the folder C:\Users\<you>\Desktop\vaani_test" -> **Deny** | folder still exists | |
| H2 | Same request -> **Approve** | folder deleted | |
| H3 | "Delete C:\Users\<you>\Desktop" | refused (protected) | |
| H4 | "Delete C:\Windows\notepad.exe" | refused (outside user folder) | |
| H5 | Tools page: turn on "Confirm every desktop action", "Open notepad" | confirmation card appears | |
| H6 | `javascript:alert(1)` as a website | refused | |

## I. Resilience
| # | Test | Expected | Result |
|---|---|---|---|
| I1 | Quit Ollama, send a message | readable error, UI stays alive | |
| I2 | Stop the backend | red dot "Backend offline"; reconnects when restarted | |
| I3 | Unplug / disable the microphone, press the mic | error message, no crash | |
| I4 | Send a message while Gemma is still answering | no crash, UI stays consistent | |

## J. Performance (fill from the reports)
Run `python scripts\log_report.py` and `python scripts\resource_report.py --seconds 90` while using the assistant.

| Metric | Median | p95 | Notes |
|---|---|---|---|
| Speech recognition, English (ms) | | | |
| Speech recognition, Tamil (ms) | | | |
| Time to first word, text (ms) | | | |
| Generation speed (tok/s) | | | |
| English speech synthesis per sentence (ms) | | | |
| Tamil speech synthesis per sentence (ms) | | | |
| Peak system RAM (MB) | | | |
| Peak GPU memory (MB) | | | |
| Gemma on GPU (%) from `ollama ps` | | | |
