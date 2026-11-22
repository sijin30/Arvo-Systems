# What I did not finish, and why

**Not done**

1. **The app is not deployed yet.** There is no live URL. The `Dockerfile` and `render.yaml`
   are written, but I could not build the image here (no Docker on this machine) and I have
   no hosting account to deploy with. They are untested. Everything else was run and checked
   locally: the API served the built frontend, and a real browser (Microsoft Edge, driven by a
   script) walked through login, taking a ticket, a private note, a reply with the clock
   paused, and the customer view.
2. **Customers cannot act for themselves.** The brief describes a screen for support agents,
   so agents log tickets and customer messages, and a customer gets a read-only page. There is
   no customer login, no inbound email, and nothing is emailed out. "Reply sent" means saved
   in the system at that moment, not delivered to an inbox.
3. **No automated tests for the React screens.** The backend has 83 tests. The screens were
   checked by hand and by one scripted browser run, which is not a regression suite.
4. **Small gaps:** no change-password or user-management screens (agents are seeded); the
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
