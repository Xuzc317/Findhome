import { StorageKey } from "@/constant";
import { getLocalStorage, setLocalStorage } from "./storage";

export function getBrowserToken() {
  const token = getLocalStorage(StorageKey.USER_TOKEN) || "";
  return token;
}

export function setBrowserToken(token: string) {
  setLocalStorage(StorageKey.USER_TOKEN, token);
}

export function getSearchHistory(): string[] {
  return JSON.parse(getLocalStorage(StorageKey.SEARCH_HISTORY) || "[]");
}

export function addSearchHistory(history: string) {
  history = history.trim();
  const historyList = getSearchHistory();
  if (historyList.includes(history) || !history) {
    return;
  }
  historyList.push(history);
  setLocalStorage(StorageKey.SEARCH_HISTORY, JSON.stringify(historyList));
}

export function clearSearchHistory() {
  setLocalStorage(StorageKey.SEARCH_HISTORY, "[]");
}


export function isLogin() {
  return !!getBrowserToken();
}