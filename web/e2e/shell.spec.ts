import { expect, test } from "@playwright/test";
import { expectAccessible } from "./helpers";

test("home lists repositories and is accessible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Repositories" })).toBeVisible();
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByTestId("loading")).toHaveCount(0);
  await expectAccessible(page);
});

test("skip link is the first tab stop and moves focus to main", async ({ page, isMobile }) => {
  test.skip(isMobile, "keyboard flow checked on desktop");
  await page.goto("/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to main content" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#main$/);
});

test("invalid repository URL is refused before any request", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (r) => r.method() === "POST" && posts.push(r.url()));
  await page.goto("/");
  await page.getByRole("textbox", { name: "Public GitHub repository URL" }).fill("https://gitlab.com/a/b");
  await page.getByRole("button", { name: "Add repository" }).click();
  await expect(page.getByRole("alert")).toContainText("not a public GitHub repository URL");
  expect(posts).toEqual([]);
});

test("unknown job id shows a not-found error, not a fake stepper", async ({ page }) => {
  await page.goto("/jobs/does-not-exist");
  await expect(page.getByRole("alert")).toContainText("not found");
  await expect(page.getByTestId("job-steps")).toHaveCount(0);
});
