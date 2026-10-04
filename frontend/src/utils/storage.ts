
function isInServer() {
  return typeof window === "undefined";
}



export function setLocalStorage(key: string, value: string) {
  if (isInServer()) {
    return;
  }
  localStorage.setItem(key, value);
}


export function getLocalStorage(key: string) {
  if (isInServer()) {
    return "";
  }
  return localStorage.getItem(key) || "";
}

export function setLocalStorageObject(key: string, value: unknown) {
  setLocalStorage(key, JSON.stringify(value));
}

export function getLocalStorageObject(key: string): unknown | null {
  try {
    const value = getLocalStorage(key);
    if (!value) return null;
    return JSON.parse(value);
  } catch (error) {
    console.error("getLocalStorageObject error", error);
    return null;
  }
}

export function removeLocalStorage(key: string) {
  if (isInServer()) {
    return;
  }
  localStorage.removeItem(key);
}