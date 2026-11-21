import { describe, expect, it } from "vitest";
import { companionDownloadUrl } from "./companion-downloads";
const origin = "https://market.example.test";
const candidate = {ready:true,version:"2.0.0-beta.1",download_url:"/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64"};
describe("controlled companion downloads", () => {
  it("keeps private beta and stable paths/version identity distinct", () => {
    expect(companionDownloadUrl(candidate,"private-beta",origin)).toBe(candidate.download_url);
    expect(companionDownloadUrl(candidate,"stable",origin)).toBeNull();
    const stable={ready:true,version:"2.0.0",download_url:"/api/v1/companion/releases/2.0.0/windows-x64"};
    expect(companionDownloadUrl(stable,"stable",origin)).toBe(stable.download_url);
    expect(companionDownloadUrl(stable,"private-beta",origin)).toBeNull();
  });
  it.each([
    "https://other.example.test/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64",
    "javascript:alert(1)","//other.example.test/download.exe",
    "https://name:secret@market.example.test/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64",
    candidate.download_url+"?token=unsafe",candidate.download_url+"#other",
    "/api/v1/companion/private-beta/2.0.0-beta.2/windows-x64",
    "/api/v1/companion/releases/2.0.0-beta.1/windows-x64",
  ])("refuses redirected, credential-bearing or mismatched destinations: %s", (download_url) => {
    expect(companionDownloadUrl({...candidate,download_url},"private-beta",origin)).toBeNull();
  });
  it("does not turn unavailable or malformed metadata into a download", () => {
    expect(companionDownloadUrl({...candidate,ready:false},"private-beta",origin)).toBeNull();
    expect(companionDownloadUrl({...candidate,version:"2.0.0-beta.0"},"private-beta",origin)).toBeNull();
    expect(companionDownloadUrl(undefined,"private-beta",origin)).toBeNull();
  });
});
