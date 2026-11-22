# What I did not finish, and why

**Not done**

1. **Hosting was done separately and I have not tested the live site.** The `Dockerfile` and
   `render.yaml` were written without being run on my machine (no Docker here). Everything
   else was run and checked locally: the API served the built frontend, and a real browser
   (Microsoft Edge, driven by a script) walked through a customer signing up and reporting a
   problem, an agent taking it, a private note, a reply with the clock paused, the customer
   answering, and the lead creating a new agent.
2. **No email at all.** Customers sign up and use the site, and the lead creates agents, but the
   app sends no email. So there is no email verification at sign-up, no "forgot password"
   link, and no notification when someone replies. "Reply sent" means saved in the system
   at that moment, not delivered to an inbox. A forgotten agent password is reset by the
   lead; a forgotten customer password cannot be reset yet.
3. **No automated tests for the React screens.** The backend has 110 tests. The screens were
   checked by hand and by one scripted browser run, which is not a regression suite.
4. **Small gaps:** a password change or reset does not end sessions that are already open
   (they expire after 12 hours); customers cannot pick a preferred agent; sign-up has no
   rate limit beyond the failed-login throttle; the
   dashboard shows the first 100 matching tickets with no paging; login throttling is kept in
   memory (one server only); the holiday list is seeded with fixed-date holidays only and the
   lead adds festival dates.

**Judgement calls the brief left open** (all listed with reasons in the README):
priority change recomputes from creation time; "half a day" is 4h 30m; "same working day"
is one full working day; "about a week" is 5 working days for auto-close and reopen.
Changing any of them is a one-line edit in `backend/app/sla.py`.

**Honest limits of the tamper-proofing:** the database refuses changes to history even for
raw SQL, but a database *owner* can switch the protection off. If that happens, the hash
chain no longer matches and the Admin page's integrity check reports where.

**About the commit history:** the commit timestamps are the real ones and were not altered.
