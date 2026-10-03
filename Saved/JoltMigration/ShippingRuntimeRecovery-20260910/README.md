# Shipping fixture startup recovery

Run `Saved/JoltMigration/Resume-FinalFightShippingRuntime.ps1` from the project directory after review. This launches only the existing Shipping package, with fresh evidence and a fresh external saved `Engine.ini`; it does not build, cook, restage, or change project defaults.

The ini contains exactly one setting:

```ini
[/Script/EngineSettings.GameMapsSettings]
GameDefaultMap=/Engine/Maps/Entry.Entry
```

The copied runner differs from its retained original only in its Common.ps1 import, an exact-content/hash check for this Shipping ini, the `-EngineINI="absolute path"` launch argument, a post-exit hash check, and the recorded ini identity. The existing staged-file, exit-code, three-fixture, saved-floor and separate ensure-count checks remain unchanged. The wrapper verifies original package/failure evidence, all candidate files, Editor/Shipping binaries, and the complete cook before/after runtime.

Pinned UE5.7 source: `Engine/Source/Runtime/Engine/Private/GameInstance.cpp:641` strips client Shipping map arguments. `Runtime/Core/Public/Misc/ConfigCacheIni.h:53` disables `-ini:` key overrides in client Shipping. The separate saved-config filename override in `Runtime/Core/Private/Misc/ConfigCacheIni.cpp:6017–6041` accepts `EngineINI=` without that guard. `ConfigContext.cpp:74–80` enables saved config for GConfig, `1137–1148` reads it, and `1227` applies it after defaults. `ConfigCacheIni.cpp:6299–6305` also loads saved config after binary-config deserialization. The generated/loose-ini restriction macros default to zero in `Runtime/Core/Public/Misc/ConfigContext.h:21–22` and `Runtime/PakFile/Private/IPlatformFilePak.cpp:72–73`.

This verifies a fixture package with an explicit runtime startup setting; it does not turn this restricted package into the production game or change the saved `/Game/mybasic` gameplay default.
