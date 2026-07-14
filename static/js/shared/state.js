let uploadStatusResetTimerId = null;
let presetStatusResetTimerId = null;
let storageBackendStatusResetTimerId = null;

export function clearUploadStatusResetTimer() {
    if (uploadStatusResetTimerId !== null) {
        window.clearTimeout(uploadStatusResetTimerId);
        uploadStatusResetTimerId = null;
    }
}

export function setUploadStatusResetTimer(timerId) {
    uploadStatusResetTimerId = timerId;
}

export function clearPresetStatusResetTimer() {
    if (presetStatusResetTimerId !== null) {
        window.clearTimeout(presetStatusResetTimerId);
        presetStatusResetTimerId = null;
    }
}

export function setPresetStatusResetTimer(timerId) {
    presetStatusResetTimerId = timerId;
}

export function clearStorageBackendStatusResetTimer() {
    if (storageBackendStatusResetTimerId !== null) {
        window.clearTimeout(storageBackendStatusResetTimerId);
        storageBackendStatusResetTimerId = null;
    }
}

export function setStorageBackendStatusResetTimer(timerId) {
    storageBackendStatusResetTimerId = timerId;
}
