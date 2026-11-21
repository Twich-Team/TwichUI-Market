import { describe,it,expect } from "vitest";
import {renderToStaticMarkup} from "react-dom/server";
import {ItemName,ITEM_QUALITY_COLORS,itemQualityColor,UNKNOWN_ITEM_COLOR} from "./item-name";
describe("verified item quality names",()=>{
  for(const [quality,color] of Object.entries(ITEM_QUALITY_COLORS)) it(`${quality} uses the authentic ${color}`,()=>{
    expect(itemQualityColor(quality)).toBe(color);
    expect(renderToStaticMarkup(<ItemName name="Verified item" quality={quality}/>)).toContain(`color:${color}`);
    expect(itemQualityColor(quality.toLowerCase())).toBe(color);
  });
  for(const quality of [null,undefined,"","MYSTERY","HEIRLOOM","WOW_TOKEN"]) it(`keeps unsupported ${quality} neutral`,()=>{
    expect(itemQualityColor(quality)).toBe(UNKNOWN_ITEM_COLOR);
    const html=renderToStaticMarkup(<ItemName name="Legendary sounding name" quality={quality}/>);
    expect(html).toContain('data-quality="unknown"');expect(html).toContain('Quality unknown');
  });
  it("escapes names and preserves their exact text",()=>{
    const html=renderToStaticMarkup(<ItemName name={'Sword <Test> & Gem'} quality="RARE"/>);
    expect(html).toContain('Sword &lt;Test&gt; &amp; Gem');
  });
});
