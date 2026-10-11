# Activity journal, accounts and sessions — 12 October 2026

## Activity center

The top-bar list icon now remains available even when the journal is empty.
Active work is sorted before terminal records, and the scrollable menu shows
the complete history instead of only eight records. Clear completed removes
finished, failed and cancelled records and their cancellation markers, while
preserving active work. Cancelling shows immediate feedback and disables repeated
requests until the owner acknowledges cancellation. Long labels and errors have
tooltips.

Each new activity records the owner's PID and its /proc start time. A terminated,
zombie or reused process is shown as Interrupted instead of running forever.
This does not detect a stuck thread inside a live process and does not terminate
the owner. Invalid timestamps, statuses, labels and progress no longer crash the
panel; update can recover a non-dictionary record.

The journal belongs to the UID, not to an individual graphical session. logind
keeps the runtime directory while that user has any session open. Distinct users
have separate journals; an account's apps intentionally share its own journal.
The cache-directory fallback also belongs to that user's home.

## Account and login fixes

- Account creation/removal executes authorization in a worker. The Users page
  prevents duplicate requests and restores availability after success or failure.
- A username edited manually is preserved when the full name changes.
- Administrator detection includes a primary sudo group, not only secondary
  memberships.
- Changing the password closes the parent's PTY on both timeout and normal exit.
- Choosing another login account clears the previous password. Account and
  session controls are disabled during authentication and restored on failure.
- greetd sockets close after success, failure or failed connection. IPC uses a
  finite timeout and rejects oversized, invalid JSON and unexpected responses,
  so protocol failures are shown as login errors instead of stranding the spinner.

## Tests and evidence

`tests/unit/test_activity_sessions.py` covers ordering, interrupted owners,
clearing/cancellation, malformed records, per-runtime isolation, administrator
groups, PTY cleanup, password switching and socket cleanup.
`tests/unit/test_greetd.py` also exercises invalid and oversized wire responses.
The preceding sources fail sixteen new regression cases; original and corrected logs
are kept under `work/audit-activity-sessions-2026-10-12/`.

The real GTK test `tests/activity-user-interactions.py` checks all thirteen rows,
cancel feedback, clearing, the empty menu, main-loop responsiveness during a
held authorization request, cancellation recovery and preserving a custom username.
It is included in `make test-system-native`.

`tests/multiuser-sessions.sh` creates actual Unix accounts only in a disposable
container. It checks standard/admin creation, promotion/demotion and removal,
starts two labwc/Aurora/Files desktops simultaneously as different UIDs on
separate buses and Wayland sockets, checks separate settings and private journals,
and verifies that logging out account A leaves account B and its job running.
The initial laboratory run needed the standard sticky /tmp/.X11-unix permissions;
that was test-environment setup, not a product failure.
`tests/logout-relogin.sh` checks a second graphical login on the same bus.

Run these native scenarios through `desktop/dev/run-headless.sh`. The account
script refuses to run outside the opted-in disposable container.

Final native run: **471 passed, one skipped** and every GTK interaction scenario
passed (`native-verified/scenario-result`: 0). The multi-account desktop test
passed (`multiuser-verified/scenario-result`: 0); sequential login on the same bus
reported `RELOGIN_OK`. Static checks passed, including regenerated translations,
schema validation and the 74-page manual (`static.log`). The light/dark/narrow
window preview passed (`style-preview/scenario-result`: 0) and its eight screenshots
were inspected for layout and readability.

`tests/interact/users_sessions.py ISO --push` stages the current desktop in an
older live image and exercises actual greetd/PAM authentication and logind in QEMU.
Its wrong-password and successful-login checks use greetd's real socket. After a
successful IPC start it ends the greeter compositor, matching the graphical
greeter's normal completion action. A second PAM session keeps the first account's
runtime/user bus alive across graphical logout and login of another account.
Omit --push when checking a newly built ISO.

The verified QEMU run passed (`vm-verified.log`: USERS AND SESSIONS PASSED).
Wrong-password rejection used real PAM; both accounts logged in graphically,
removing the active account was refused, and logind listed a graphical user
session and a distinct background PAM session for account A. Its background
session remained active while account B logged in and after A logged in again.
Preferences remained independent/persistent and collected shell logs had no
Python traceback or GTK critical error. The first run assumed a fixed socket
path; the test now reads GREETD_SOCK from the actual greeter environment.

The full application smoke run passed (`smoke/scenario-result` and
`smoke/smoke/result`: 0): all Aurora apps, all 27 Settings pages, Spotlight,
Launchpad, Quick Look, overview, clipboard, Assistant and widget popovers.
No Python tracebacks or GTK critical errors were found in its logs.

## Window appearance refresh

Shared GTK 4 window chrome uses cool neutral light surfaces and charcoal dark
surfaces, thin card outlines and separators, softer active/backdrop shadows,
rounded progress bars, explicit keyboard focus and selected-sidebar cues.
Settings adds gently tinted icon tiles and consistent sidebar spacing. GTK 3
controls and navigation rows receive matching rounding. Existing user choices
for corner radius and title-bar buttons retain priority. The per-app surface
palette clears itself when high contrast is active and listens for live changes.

`tests/window-style-preview.sh` validates the shared CSS with GTK and captures
Settings, Files and Task Manager in light/dark, plus collapsed Settings at 480 px.
Full app smoke checks cover the broader set of windows. Applications drawing
their own interfaces, such as Electron/web apps, keep their own content styling.

## Remaining scope

Two simultaneous graphical desktops for the same account are unsupported: shell
and application GApplication IDs are shared on that UID's user bus. Distinct
account desktops are isolated. Sequential same-account login and concurrent
non-graphical sessions are separate cases and are tested explicitly.
There is no graphical fast-user-switching control; the supported ordinary flow
is Log Out → select another account at the login screen.

The QEMU run stages sources into the old ISO; this is not a release test of a
new ISO. A rebuilt image is still needed for final image-level validation.
