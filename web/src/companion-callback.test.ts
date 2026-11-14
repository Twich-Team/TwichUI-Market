import { describe, it, expect } from "vitest";
import { companionCallback } from "./companion-callback";
const state = "S".repeat(43),
  code = "C".repeat(43),
  good = `http://127.0.0.1:43123/companion/callback?code=${code}&state=${state}`;
describe("native return navigation", () => {
  it("accepts an exact ephemeral loopback code or denial", () => {
    expect(companionCallback(good)).toBe(good);
    expect(
      companionCallback(good.replace(`code=${code}`, "error=access_denied")),
    ).toContain("error=access_denied");
  });
  it.each([
    good.replace("127.0.0.1", "localhost"),
    good.replace("127.0.0.1", "attacker.example"),
    good.replace("http:", "https:"),
    good.replace(":43123", ":80"),
    good.replace(":43123", ":043123"),
    good.replace("/companion/callback", "/companion/%63allback"),
    good.replace("127.0.0.1", "user:password@127.0.0.1"),
    good + "#fragment",
    good + "&extra=value",
    good + "&state=" + state,
    good.replace(code, "short"),
    good.replace(state, "short"),
    good.replace(`code=${code}`, "error=invalid_grant"),
    good + "&error=access_denied",
  ])("rejects a foreign or ambiguous return address", (value) => {
    expect(() => companionCallback(value)).toThrow();
  });
});
