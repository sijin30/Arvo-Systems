# Hi sir these are the things what I did not finish, and why

I focused on getting the core ticket workflow, working-hours SLA logic, key safeguards (single-agent ticket claiming, strict separation of internal notes from customer views, and tamper-evident history), and the live deployment working first. Because of that, several extras and edge-case details were left out or kept minimal.

## Intentionally left out

- **No email integration:** Customers sign up, submit issues, and reply inside the portal, and leads create agent accounts directly in the app. I skipped outgoing/incoming email, email verification, email password resets (leads can reset an agent's password; customer password reset isn't built yet), and email notifications. When a reply shows as sent here, it is saved and timestamped in Frontdesk rather than sent to an external inbox.
- **Smaller operational & UI shortcuts:**
  - Changing or resetting a password does not immediately revoke existing active sessions; current tokens simply expire after 12 hours.
  - Customers cannot pick a preferred agent when opening a ticket—new tickets go into the shared unassigned queue so claiming stays single-owner.
  - Sign-up does not have a dedicated rate limit beyond the login failure throttle, and that login throttle is stored in memory on a single instance.
  - The ticket list caps at the first 100 matching tickets instead of using pagination.
  - Only fixed-date national holidays are pre-seeded; shifting festival dates are added manually by the lead on the Admin page.

## Open edge cases & commit history

- **Ambiguous rules:** Where the story left room for interpretation, I documented my SLA calculations, working-hour rules, and audit tamper-proofing assumptions in `README.md` (with SLA math isolated in `backend/app/sla.py`).
- **Commit history:** Git commit timestamps reflect the actual development timeline and were left untouched.
