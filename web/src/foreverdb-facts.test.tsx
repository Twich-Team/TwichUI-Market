import { renderToStaticMarkup } from 'react-dom/server';
import { describe,it,expect } from 'vitest';
import { ForeverDBFacts } from './foreverdb-facts';
describe('ForeverDB qualified facts',()=>{
 it('shows exact stats, units, effects and reference-only disenchant chances',()=>{
  const html=renderToStaticMarkup(<ForeverDBFacts facts={{stats:[{stat_id:4,label:'Strength',value:5}],weapon:{damage:{min:'22',max:'42',school:'Physical'},speed_seconds:'2.1'},effects:[{spell_id:1,trigger:'use',text:'<script>escaped</script>'}],disenchant:{source:'Classic data, not confirmed in Forever',results:[{itemId:2,name:'Dust',min:1,max:2,chancePercent:75}]}}}/>);
  expect(html).toContain('+5');expect(html).toContain('Strength');expect(html).toContain('2.1');expect(html).toContain('seconds');expect(html).toContain('Classic data, not confirmed');expect(html).toContain('reference chance');expect(html).not.toContain('<script>');expect(html).toContain('&lt;script&gt;');
 });
 it('keeps historical and uncertain availability visible and unknown quantities unknown',()=>{
  const html=renderToStaticMarkup(<ForeverDBFacts facts={{availability:{betaEvent:true,speculation:true,speculationReasons:['Synthetic uncertainty'],dataFromBuild:'1.60.1.70888'},crafting:[{profession:'alchemy',profession_name:'Alchemy',source:{build:'1.60.1.70938'},recipe:{spellId:3,name:'Fixture potion',makes:{itemId:1,name:'Potion'},reagents:[{itemId:2,name:'Herb',count:2}],learnedFrom:{sources:{chancePercent:null,note:'Classic data unless seenInForever'}}}}]}}/>);
  expect(html).toContain('Historical beta');expect(html).toContain('Details retained from build');expect(html).toContain('Synthetic uncertainty');expect(html).toContain('Unknown quantity');expect(html).toContain('Classic data unless seenInForever');
 });
});
