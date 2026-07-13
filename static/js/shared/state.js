let uploadStatusResetTimerId = null;
let presetStatusResetTimerId = null;

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
