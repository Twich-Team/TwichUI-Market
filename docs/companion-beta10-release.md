# Companion beta.10 publication

The owner instructed “Okay then do it” after the new Companion release requirements were explained. This authorizes publication through the existing private signed-update channel, with prior releases and the current updater key preserved. It does not authorize addon publication, provider/collector/retention/backup policy changes or a new real-client acceptance claim.

Payload source is frozen at `be09ff9f8adc1d5c8b8c12d04032b954863aa553`, based on reviewed PR41 merge `3b2e9ece3f1ef0f9c3ba4c8e16ed2fa439a8e891`. Only consistent beta.10 identities and the actual merged addon pin `074435e` change after the reviewed implementation. Core UI files match the authorized repair baseline `8dfa511`.

The release keeps Workshop preparation within one sync run, writes data while the game is open, negotiates history contract 2 and migrates grouping/icon metadata. Files saved remains distinct from in-game consumption; first-install discovery/reload and actual Forever frame/GC behavior remain unverified. The existing private-channel tray/normal-UAC/physical-PC limitations remain explicit.

Exact payload backend/website/Windows checks, immutable installer acquisition, local original-byte signing, independent signature/version verification and actual signed SDK upgrade are required before pointer publication. Current production APIs remain on `428f0acf`; no service replacement is needed to publish the client.
