; Remove only this installation's explicit, current-user startup entry.
; Updater installs preserve the existing entry. AppData/cache/vault are never deleted here.
!macro NSIS_HOOK_PREUNINSTALL
  ${If} $UpdateMode != 1
    Push $R0
    ReadRegStr $R0 HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "TwichUI Market Companion DEV"
    ${If} $R0 == '$\"$INSTDIR\twichui-market-companion-dev.exe$\" --background'
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "TwichUI Market Companion DEV"
      DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run" "TwichUI Market Companion DEV"
    ${EndIf}
    Pop $R0
  ${EndIf}
!macroend
