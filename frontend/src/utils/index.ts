import { SITE_NAME } from "@/constant";

export function getPageTitle(title?: string) {
  if (!title) {
    return SITE_NAME;
  }
  return `${title} - ${SITE_NAME}`;
}