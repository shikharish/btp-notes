
- reproduced using `rfp_camera_repro.html`
  - runtime config

    ```text
    privacy.resistFingerprinting = true
    privacy.fingerprintingProtection = false
    ```

  - first click "Start camera", then "2D getImageData -> putImageData"
  - glitch seen

- when `privacy.resistFingerprinting = true`
  - `nsRFPService::IsRFPEnabledFor()` returns true
  - `toolkit/components/resistfingerprinting/nsRFPService.cpp:254-260`

- result of `IsRFPEnabledFor()`
  - used by `Document::ShouldResistFingerprinting()`
  - `dom/base/Document.cpp:16920-16923`

  ```cpp
  bool Document::ShouldResistFingerprinting(RFPTarget aTarget) const {
    return mShouldResistFingerprinting &&
           nsRFPService::IsRFPEnabledFor(this->IsInPrivateBrowsing(), aTarget,
                                         mOverriddenFingerprintingSettings);
  }
  ```

- `rr` recorded `mShouldResistFingerprinting = true`
- `IsRFPEnabledFor(...) = true`
- result: `Document::ShouldResistFingerprinting(...) = true`

- `IsImageExtractionAllowed()` checks the document RFP targets
  - `dom/canvas/CanvasUtils.cpp:175-183`

  ```cpp
  // -------------------------------------------------------------------
  // Check if we will do any further blocking

  if (!aDocument->ShouldResistFingerprinting(
          RFPTarget::CanvasImageExtractionPrompt) &&
      !aDocument->ShouldResistFingerprinting(
          RFPTarget::CanvasExtractionBeforeUserInputIsBlocked)) {
    return true;
  }
  ```

- `CanvasImageExtractionPrompt = true` , `CanvasExtractionBeforeUserInputIsBlocked = true`
  - they are `true` because `privacy.resistFingerprinting = true`
- branch is `false`

- canvas permission checked next
  - `dom/canvas/CanvasUtils.cpp:185-195`

  ```cpp
  // -------------------------------------------------------------------
  // Check a site's permission

  // If the user has previously granted or not granted permission, we can return
  // immediately. Load Permission Manager service.
  uint64_t permission = GetCanvasExtractDataPermission(aPrincipal);
  switch (permission) {
    case nsIPermissionManager::ALLOW_ACTION:
      return true;
    case nsIPermissionManager::DENY_ACTION:
      return false;
  ```

- recorded `permission = 2` , `2 = nsIPermissionManager::DENY_ACTION`
- because i selected "Deny" when firefox popped dialog for canvas extraction
- result: `IsImageExtractionAllowed() = false`

- in `ImageExtractionResult()`
  - `dom/canvas/CanvasUtils.cpp:278-280`

  ```cpp
  nsCOMPtr<dom::Document> ownerDoc = aCanvasElement->OwnerDoc();
  if (!IsImageExtractionAllowed(ownerDoc, aCx, aPrincipal)) {
    return ImageExtraction::Placeholder;
  }
  ```

- `GetImageDataArray()` receives `ImageExtraction::Placeholder`
  - extraction decision done in `dom/canvas/CanvasRenderingContext2D.cpp:6371-6380`
  - placeholder copied to `ImageData.data`: `dom/canvas/CanvasRenderingContext2D.cpp:6422-6423`
  - placeholder implementation: `dom/canvas/GeneratePlaceholderCanvasData.h`

- test page receives the placeholder from `getImageData()`
  - same `ImageData` passed to `putImageData()`
  - result: placeholder visible as the glitch

- rr/GDB evidence:
  - `mShouldResistFingerprinting = true`
  - canvas permission = `2` / `DENY_ACTION`
  - `IsImageExtractionAllowed() = false`
  - `ImageExtractionResult() = Placeholder`
  - placeholder branch was entered

- for testing: added a line to change `CanvasUtils::ImageExtraction::Placeholder` to `CanvasUtils::ImageExtraction::Unrestricted` in `CanvasRenderingContext2D.cpp`
  - rebuild and reran the test, with same config
  - no glitch seen
