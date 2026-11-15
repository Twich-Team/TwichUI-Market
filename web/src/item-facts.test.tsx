import {expect,it} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import {ItemFacts,type ItemProfile} from './item-components';
it('keeps verified facts and all unique credits visible while provenance is optional',()=>{
 const credit={text:'Data from Everloot, CC BY-SA 4.0',url:'https://everloot.app',notice:'Game data © Blizzard Entertainment'};
 const profile={item_id:1,name:'Verified sword',quality:'RARE',metadata_provider:'everloot',attributes:{level:20,slot:'Main Hand',subclass:'Sword',lines:[{kind:'stat',text:'+5 Strength'}],vendor_sell:'12345'},source:{provider:'everloot',confidence:'player_consensus',build:'1.60.1',observed_at:'2026-11-15T00:00:00Z'},catalog:{provenance:{name:{provider:'everloot',confidence:'player_consensus',build:'1.60.1',attribution:credit},slot:{provider:'everloot',confidence:'player_consensus',build:'1.60.1',attribution:credit}},conflicts:[]}} as unknown as ItemProfile;
 const html=renderToStaticMarkup(<ItemFacts profile={profile}/>);
 expect(html).toContain('Item Level 20');expect(html).toContain('+5 Strength');expect(html).toContain('Main Hand');expect(html).toContain('Vendor sell:');
 expect(html.match(/Data from Everloot/g)).toHaveLength(1);expect(html).toContain('Game data © Blizzard Entertainment');expect(html).toContain('<details class="item-technical"><summary>Technical details</summary>');
 expect(html.indexOf('Field provenance')).toBeGreaterThan(html.indexOf('<details'));expect(html.slice(0,html.indexOf('<details'))).not.toContain('1.60.1');
});
