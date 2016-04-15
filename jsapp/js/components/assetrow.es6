import React from 'react/addons';
import {Navigation} from 'react-router';
import $ from 'jquery';

import bem from '../bem';
import ui from '../ui';
import stores from '../stores';
import {
  formatTime,
  anonUsername,
  t,
  assign,
} from '../utils';

var AssetTypeIcon = bem.create('asset-type-icon');

var AssetRow = React.createClass({
  mixins: [
    Navigation
  ],
  clickAsset (evt) {
    var clickedActionIcon = $(evt.target).closest('[data-action]').get(0);
    if (clickedActionIcon && this.props.isSelected) {
      this.props.onActionButtonClick(assign(evt, {
        actionIcon: clickedActionIcon,
      }));
    } else {
      // this click was not intended for a button
      evt.nativeEvent.preventDefault();
      evt.nativeEvent.stopImmediatePropagation();
      evt.preventDefault();

      // if no asset is selected, then this asset
      // otherwise, toggle selection (unselect if already selected)
      let forceSelect = (stores.selectedAsset.uid === false);
      stores.selectedAsset.toggleSelect(this.props.uid, forceSelect);
    }
  },
  preventDefault (evt) {
    evt.preventDefault();
  },
  render () {
    var selfowned = this.props.owner__username === this.props.currentUsername;
    // var perm = this.props.perm;
    var isPublic = this.props.owner__username === anonUsername;
    var _rc = this.props.summary && this.props.summary.row_count;
    var isCollection = this.props.kind === 'collection',
        hrefTo = isCollection ? 'collection-page' : 'form-landing',
        hrefKey = isCollection ? 'uid' : 'assetid',
        hrefParams = {},
        tags = this.props.tags || [];
    if (isCollection) {
      _rc = this.props.assets_count + this.props.children_count;
    }
    var isDeployable = !isCollection && this.props.asset_type && this.props.asset_type === 'survey';
    hrefParams[hrefKey] = this.props.uid;
    return (
        <bem.AssetRow m={{
                            'selected': this.props.isSelected,
                            'active': this.props.isSelected,
                            'inactive': !this.props.isSelected,
                            'deleted': this.props.deleted,
                            'deleting': this.props.deleting,
                          }}
                        onClick={this.clickAsset}
                      >
          <i />

          <bem.AssetRow__cell m={['icon']}>
            <AssetTypeIcon m={[this.props.asset_type, 'medium']}><i /></AssetTypeIcon>
          </bem.AssetRow__cell>

          <bem.AssetRow__celllink m={['name', this.props.name ? 'titled' : 'untitled']}
                data-kind={this.props.kind}
                data-asset-type={this.props.kind}
                href={this.makeHref( hrefTo, hrefParams)}
              >
            <bem.AssetRow__name>
              <ui.AssetName {...this.props} />
            </bem.AssetRow__name>
          </bem.AssetRow__celllink>
          <bem.AssetRow__cellmeta>
            <bem.AssetRow__cell m={'deployment-status'}>
              {
                this.props.deployed_version_id === null ?
                  t('draft') :
                  t('deployed')
              }
            </bem.AssetRow__cell>
            <bem.AssetRow__cell m={'userlink'}>
              {
                selfowned ?
                  t('me') :
                  this.props.owner__username
              }
            </bem.AssetRow__cell>
            <bem.AssetRow__cell m={'date-modified'}>
              <span className="date date--modified">{t('Modified')} {formatTime(this.props.date_modified)}</span>
            </bem.AssetRow__cell>
            <bem.AssetRow__cell m={'row-count'}>
              {function(){
                if (this.props.kind === 'collection') {
                  return t('collection with ___ items').replace('___', _rc);
                } else if (this.props.asset_type === 'survey') {
                  return t('survey with ___ questions').replace('___', _rc);
                } else if (this.props.asset_type === 'block') {
                  return t('block with ___ questions').replace('___', _rc);
                }
              }.call(this)}
            </bem.AssetRow__cell>
          </bem.AssetRow__cellmeta>
          { this.props.isSelected &&
            <bem.AssetRow__cell m={'buttons'}>
              <bem.AssetRow__cell m={'action-icons'}>
                { this.props.kind === 'asset' &&
                  ['edit', 'view', 'download', 'clone'].map((actn)=>{
                    return (
                          <bem.AssetRow__actionIcon
                              m={actn}
                              data-action={actn}
                              data-asset-type={this.props.kind}
                              data-disabled={false}
                              >
                            <i />
                            {t(actn)}
                          </bem.AssetRow__actionIcon>
                        );
                  })
                }
                { isDeployable &&
                  <bem.AssetRow__actionIcon
                        m={'deploy'}
                        data-action={'deploy'}
                        data-asset-type={this.props.kind}
                      >
                    <i />
                    {this.props.deployed_version_id === null ?
                       t('deploy') : t('redeploy')}
                  </bem.AssetRow__actionIcon>
                }
                { this.props.kind === 'collection' &&
                ['view', 'sharing'].map((actn)=>{
                    return (
                          <bem.AssetRow__actionIcon
                            m={actn === 'view' ? 'view-collection' : actn}
                              data-action={actn}
                              data-asset-type={this.props.kind}
                              data-disabled={false}
                              >
                            <i />
                            {actn}
                          </bem.AssetRow__actionIcon>
                        );
                  })
                }
              </bem.AssetRow__cell>
            </bem.AssetRow__cell>
          }
          { tags.length > 0 && this.props.isSelected &&
            <bem.AssetRow__cellmeta m={'tags'}>
              <bem.AssetRow__cell m={'tags'}>
                <bem.AssetRow__tags>
                  <i />
                  {tags.map((tag)=>{
                    return (
                          <bem.AssetRow__tags__tag>{tag}</bem.AssetRow__tags__tag>
                      );
                  })}
                </bem.AssetRow__tags>
              </bem.AssetRow__cell>
            </bem.AssetRow__cellmeta>
          }
          { this.props.isSelected &&
            <bem.AssetRow__cell m={'secondary-buttons'}>
              <bem.AssetRow__cell m={'action-icons'}>
                  {['refresh', 'delete'].map((actn)=>{
                    return (
                          <bem.AssetRow__actionIcon
                              m={actn}
                              data-action={actn}
                              data-asset-type={this.props.kind}
                              data-disabled={false}
                              >
                            <i />
                            {t(actn)}
                          </bem.AssetRow__actionIcon>
                        );
                  })}
              </bem.AssetRow__cell>
            </bem.AssetRow__cell>
          }
        </bem.AssetRow>
      );
  }
});

export default AssetRow;
