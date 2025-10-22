import json
import zipfile
from io import BytesIO, TextIOWrapper
from pathlib import Path
from typing import Any

from calver import get_version_number
from github import download_release_archive, get_latest_release_version
from models import Attribute, HtmlData, Reference, Value, ValueSet

OUTPUT_DIRECTORY = (Path(__file__).parent.parent / 'extension-data').resolve()


def main():
    htmx_atom_feed = 'https://github.com/bigskysoftware/htmx/releases.atom'
    htmx_version = get_latest_release_version(htmx_atom_feed).lstrip('v')

    htmx_archive_url = f'https://github.com/bigskysoftware/htmx/archive/refs/tags/v{htmx_version}.zip'
    release_archive = download_release_archive(htmx_archive_url)

    attribute_names = get_attribute_names(release_archive, htmx_version)
    attributes_with_descriptions = get_descriptions(attribute_names, release_archive, htmx_version)
    global_attributes = get_global_attributes(attributes_with_descriptions)
    value_sets = get_value_sets()

    hx_complete_atom_feed = 'https://github.com/pfeif/hx-complete/releases.atom'
    hx_complete_version = get_latest_release_version(hx_complete_atom_feed)

    hx_complete_archive_url = f'https://github.com/pfeif/hx-complete/archive/refs/tags/{hx_complete_version}.zip'
    hx_complete_archive = download_release_archive(hx_complete_archive_url)

    package_manifest = get_package_manifest(hx_complete_archive)

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    write_html_data(global_attributes, value_sets)
    write_package_manifest(package_manifest, htmx_version)


def get_attribute_names(archive: bytes, version: str) -> list[str]:
    """
    Extract the htmx attribute names from the release's web docs.

    :param bytes archive: a binary release ZIP file
    :param str version: the htmx version in the format `{MAJOR}.{MINOR}.{PATCH}`

    :returns: a list of htmx attributes
    """
    attributes: list[str] = []

    with zipfile.ZipFile(BytesIO(archive)) as source_code:
        attributes_path = f'htmx-{version}/www/content/attributes'

        for filename in source_code.namelist():
            if filename.startswith(f'{attributes_path}/hx-') and filename.endswith('.md'):
                attribute = filename.removeprefix(f'{attributes_path}/').removesuffix('.md')
                attributes.append(attribute)

    if not attributes:
        raise SystemExit

    return attributes


def get_descriptions(attributes: list[str], archive: bytes, version: str) -> dict[str, str]:
    """
    Extract descriptions for htmx attributes from the reference section of the release's web docs,
    and pair them with their attributes.

    :param list[str] attributes: a list of htmx attributes
    :param bytes archive: a binary release ZIP file
    :param str version: the htmx version in the format `{MAJOR}.{MINOR}.{PATCH}`

    :returns: a dictionary where the keys are attributes and the values are attribute descriptions
    """
    lines: list[str] = []

    try:
        with zipfile.ZipFile(BytesIO(archive)) as source_code:
            with source_code.open(f'htmx-{version}/www/content/reference.md') as binary_file:
                with TextIOWrapper(binary_file, encoding='utf-8') as file_content:
                    lines = file_content.readlines()
    except KeyError:
        raise SystemExit

    remaining_attributes = attributes.copy()
    descriptions: dict[str, str] = {}

    for line in lines:
        if not line.strip().startswith('| ['):
            continue

        for attribute in remaining_attributes:
            if line.strip().startswith(f'| [`{attribute}'):
                descriptions[attribute] = line.split('|')[2].strip()
                remaining_attributes.remove(attribute)
                break

        if not remaining_attributes:
            break

    if not descriptions:
        raise SystemExit

    return descriptions


def get_global_attributes(attributes: dict[str, str]) -> list[Attribute]:
    """
    Create the global attributes for the extension's `html-data.json` file.

    :param dict[str, str] attributes: an htmx attribute/description dictionary

    :returns: a list of global attributes
    """
    global_attributes: list[Attribute] = []

    for name, description in attributes.items():
        if '@/' in description:
            description = description.replace('@/', 'https://htmx.org/')

        if '.md' in description:
            description = description.replace('.md', '/')

        for prefix in ['', 'data-']:
            attribute = Attribute(
                f'{prefix}{name}',
                description,
                name if name in ['hx-swap', 'hx-swap-oob', 'hx-target'] else None,
                [Reference(f'`{name}` documentation on htmx.org', f'https://htmx.org/attributes/{name}/')],
            )

            global_attributes.append(attribute)

    return global_attributes


def get_value_sets() -> list[ValueSet]:
    """
    Get the value sets for the `html-data.json` file.

    :returns: a list of value sets
    """
    # TODO: Think about ways to automate this.

    hx_swap = ValueSet('hx-swap')
    hx_swap_oob = ValueSet('hx-swap-oob', [Value('true')])
    hx_target = ValueSet('hx-target')

    swap_values = [
        Value('innerHTML', 'Replace the inner html of the target element'),
        Value('outerHTML', 'Replace the entire target element with the response'),
        Value('textContext', 'Replace the text content of the target element, without parsing the response as HTML'),
        Value('beforebegin', 'Insert the response before the target element'),
        Value('afterbegin', 'Insert the response before the first child of the target element'),
        Value('beforeend', 'Insert the response after the last child of the target element'),
        Value('afterend', 'Insert the response after the target element'),
        Value('delete', 'Deletes the target element regardless of the response'),
        Value('none', 'Does not append content from response (out of band items will still be processed).'),
    ]

    target_values = [
        Value(
            '<CSS query selector>',
            'A CSS query selector of the element to target.',
        ),
        Value(
            'this',
            '`this` which indicates that the element that the `hx-target` attribute is on is the target.',
        ),
        Value(
            'closest <CSS selector>',
            '`closest <CSS selector>` which will find the [closest](https://developer.mozilla.org/docs/Web/API/Element/closest) ancestor element or itself, that matches the given CSS selector (e.g. `closest tr` will target the closest table row to the element).',
        ),
        Value(
            'find <CSS selector>',
            '`find <CSS selector>` which will find the first child descendant element that matches the given CSS selector.',
        ),
        Value(
            'next',
            '`next` which resolves to [element.nextElementSibling](https://developer.mozilla.org/docs/Web/API/Element/nextElementSibling)',
        ),
        Value(
            'next <CSS selector>',
            '`next <CSS selector>` which will scan the DOM forward for the first element that matches the given CSS selector. (e.g. `next .error` will target the closest following sibling element with `error` class)',
        ),
        Value(
            'previous',
            '`previous` which resolves to [element.previousElementSibling](https://developer.mozilla.org/docs/Web/API/Element/previousElementSibling)',
        ),
        Value(
            'previous <CSS selector>',
            '`previous <CSS selector>` which will scan the DOM backwards for the first element that matches the given CSS selector. (e.g. `previous .error` will target the closest previous sibling with `error` class)',
        ),
    ]

    for swap_value in swap_values:
        hx_swap.values.append(swap_value)
        hx_swap_oob.values.append(swap_value)

        if swap_value.name != 'none':
            hx_swap_oob.values.append(Value(f'{swap_value.name}:<CSS selector>', swap_value.description))

    for target_value in target_values:
        hx_target.values.append(target_value)

    return [hx_swap, hx_swap_oob, hx_target]


def get_package_manifest(archive: bytes) -> dict[str, Any]:
    """
    Extract a `package.json` from a ZIP archive and return it as a dictionary.

    :param bytes archive: the downloaded ZIP archive

    :return: a dictionary representing the `package.json` manifest
    """
    package_manifest: dict[str, Any] = dict()

    with zipfile.ZipFile(BytesIO(archive)) as source_code:
        try:
            package_manifest_path = next(name for name in source_code.namelist() if name.endswith('package.json'))
        except StopIteration:
            raise SystemExit

        with source_code.open(package_manifest_path) as binary_file:
            with TextIOWrapper(binary_file, encoding='utf-8') as file_content:
                package_manifest = json.load(file_content)

    return package_manifest


def write_html_data(global_attributes: list[Attribute], value_sets: list[ValueSet]) -> None:
    """
    Update the extension's `htmx2.html-data.json` file.

    :param list[Attribute] global_attributes: the htmx attributes
    :param list[ValueSet] value_sets: the sets of values associated with attributes
    """
    html_data = HtmlData(global_attributes, value_sets).as_dict()

    html_data_path = OUTPUT_DIRECTORY / 'htmx2.html-data.json'

    with html_data_path.open('w') as file:
        json.dump(html_data, file, indent=4)


def write_package_manifest(package_manifest: dict[str, Any], htmx_version: str) -> None:
    """
    Update the extension's `package.json` version.
    """
    version = get_version_number()

    package_manifest_path = OUTPUT_DIRECTORY / 'package.json'

    package_manifest['version'] = version
    package_manifest['htmxVersion'] = htmx_version

    with package_manifest_path.open('w') as file:
        json.dump(package_manifest, file, indent=4)


if __name__ == '__main__':
    main()
