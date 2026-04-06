<div align="center">

<h1>autofyn</h1>

**স্বয়ংক্রিয় কোডিং এজেন্ট। একটি রিপো দিন, একটি PR ফেরত পান।**

দীর্ঘমেয়াদী সেশন · স্যান্ডবক্সড এক্সিকিউশন · লাইভ তত্ত্বাবধান

<img src="assets/ui.png" width="800" alt="AutoFyn মনিটর" />

<br/>

<img src="assets/autofyn-working.png" width="800" alt="AutoFyn কাজ করছে" />

</div>

🌐 [English](README.md)

---

## পূর্বশর্ত

- Docker এবং Docker Compose
- Anthropic API কী ([console.anthropic.com](https://console.anthropic.com))
- GitHub পার্সোনাল অ্যাক্সেস টোকেন (repo স্কোপ)

একটি কাজ সেট করুন, সময়সীমা নির্ধারণ করুন, চলে যান। ৩০ মিনিট বা ৮+ ঘণ্টা চালান — এটি পরিকল্পনা করে, তৈরি করে, পর্যালোচনা করে এবং সময় শেষ না হওয়া পর্যন্ত কমিট করতে থাকে। কোড বিচ্ছিন্ন স্যান্ডবক্সে চলে এবং কখনও আপনার মেশিনে চলে না।

## দ্রুত শুরু

```bash
git clone https://github.com/SignalPilot-Labs/autofyn.git
cd autofyn && ./install.sh             # CLI ইনস্টল + Docker ইমেজ তৈরি করে
autofyn start                          # সার্ভিসগুলো শুরু করুন
```

বিদ্যমান ইনস্টল আপডেট করতে: `autofyn update`

### কনফিগার করুন

CLI বা ওয়েব UI এর মাধ্যমে [http://localhost:3400](http://localhost:3400):

```bash
autofyn settings set --claude-token YOUR_ANTHROPIC_KEY --git-token YOUR_GITHUB_TOKEN --github-repo owner/repo
```

### চালান

```bash
autofyn run new -p "Fix authentication bugs" -d 30
```

*(`-p` ফ্ল্যাগে আপনার কাজের বিবরণ ইংরেজিতে বা বাংলায় লিখুন)*

আপনি যদি একটি git রিপোর ভিতরে থাকেন, autofyn স্বয়ংক্রিয়ভাবে সনাক্ত করে — `--github-repo` নির্দিষ্ট করার প্রয়োজন নেই:

```bash
cd your-project/
autofyn run new -p "Fix authentication bugs" -d 30
```

*(`-p` ফ্ল্যাগে আপনার কাজের বিবরণ ইংরেজিতে বা বাংলায় লিখুন)*

### পর্যবেক্ষণ করুন

CLI ব্যবহার করুন বা [http://localhost:3400](http://localhost:3400) খুলুন।

```bash
autofyn run                            # ইন্টারেক্টিভ রান সিলেক্টর
autofyn run get <run_id>               # রানের বিস্তারিত + অ্যাকশন মেনু
```

## CLI রেফারেন্স

```
# সার্ভিস
autofyn start                          # সার্ভিসগুলো শুরু করুন (দ্রুত, রিবিল্ড ছাড়া)
autofyn stop                           # সব সার্ভিস বন্ধ করুন
autofyn update                         # সর্বশেষ কোড টানুন + ইমেজ পুনর্নির্মাণ করুন
autofyn logs                           # সব কন্টেইনার লগ স্ট্রিম করুন (Ctrl+C থামাতে)
autofyn logs 50                        # শেষ ৫০ লাইন দেখুন + ফলো করুন
autofyn kill                           # সব কন্টেইনার মুছে ফেলুন

# রান
autofyn run                            # ইন্টারেক্টিভ রান সিলেক্টর
autofyn run new -p "Fix auth bugs"     # একটি নতুন রান শুরু করুন
autofyn run list                       # সাম্প্রতিক রানগুলো দেখুন
autofyn run get <run_id>               # রানের বিস্তারিত + অ্যাকশন মেনু দেখুন

# সেটিংস ও কনফিগ
autofyn settings status                # ক্রেডেনশিয়াল কনফিগ পরীক্ষা করুন
autofyn settings get                   # সব সেটিংস দেখুন (মাস্কড)
autofyn settings set --claude-token TOKEN --git-token TOKEN --github-repo owner/repo

# রিপো (স্থানীয় git রিপো স্বয়ংক্রিয়ভাবে সনাক্ত করে)
autofyn repos list                     # রান সংখ্যাসহ রিপো তালিকা
autofyn repos detect                   # বর্তমান ডিরেক্টরিতে git রিপো সনাক্ত করুন
autofyn repos set-active owner/repo    # সক্রিয় রিপো সেট করুন
autofyn repos remove owner/repo        # একটি রিপো সরান

# এজেন্ট
autofyn agent health                   # এজেন্টের অবস্থা পরীক্ষা করুন
autofyn agent branches                 # git ব্রাঞ্চের তালিকা

# CLI কনফিগ
autofyn config get                     # CLI কনফিগ দেখুন
autofyn config set --api-key KEY       # CLI কনফিগ আপডেট করুন
```

মেশিন-পাঠযোগ্য আউটপুটের জন্য যেকোনো কমান্ডে `--json` ব্যবহার করুন।

---

[Claude Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk) দিয়ে তৈরি। MIT লাইসেন্স।
