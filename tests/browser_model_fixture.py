"""UI fixture: construct source models from a synthetic Site repository only."""
from site_renderer import repository_browser as browser
from publication_bundle.source_reader import collect_records
import subprocess

def generate_browser(repository, output, fixtures):
    root=browser.prepare_browser_root(output)
    browser.write_root_index(root,tuple(fixtures));browser.write_browser_controller(root)
    messages=[]
    for name,source in fixtures.items():
        revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
        tree,records=collect_records('site',repository,revision,source)
        target=root/name;target.mkdir()
        (target/'index.html').write_text(browser.render_browser_page(name,revision,tree,records,tuple(fixtures)))
        for record in records.values():browser.write_verified_file_page(target/record.viewer_url,name,revision,record)
        messages.append(name)
    return messages
