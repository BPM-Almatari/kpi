import React from "react";
import Reflux from "reflux";
import reactMixin from "react-mixin";
import autoBind from "react-autobind";
import bem from "../../bem";
import classNames from "classnames";
import Select from "react-select";
import alertify from "alertifyjs";
import stores from "../../stores";
import actions from "../../actions";
import mixins from "../../mixins";
import { t } from "../../utils";

class CopyTeamPermissions extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      isImportButtonEnabled: false,
      isAwaitingAssetChange: false,
      isCopyFormVisible: false,
      sourceUid: null,
      sourceName: null,
      targetUid: this.props.uid,
      targetName: stores.allAssets.byUid[this.props.uid].name
    };
    this.store = stores.allAssets;
    autoBind(this);
  }

  componentDidMount() {
    this.listenTo(stores.asset, this.onAssetChange);
  }

  onAssetChange(data) {
    if (data[this.state.targetUid] && this.state.isAwaitingAssetChange) {
      this.setState({ isAwaitingAssetChange: false });
      this.refreshImportButton();
    }
  }

  refreshImportButton() {
    this.setState({
      isImportButtonEnabled:
        this.state.sourceUid !== null && !this.state.isAwaitingAssetChange
    });
  }

  showCopyForm() {
    this.setState({ isCopyFormVisible: true });
  }

  updateTeamPermissionsInput(asset) {
    if (asset !== null) {
      this.setState({
        sourceUid: asset.value,
        sourceName: stores.allAssets.byUid[asset.value].name
      });
      this.refreshImportButton();
    }
  }

  safeCopyPermissionsFrom() {
    if (this.state.sourceUid) {
      const dialog = alertify.dialog("confirm");
      const finalMessage = t("You are about to copy permissions from ##source to ##target. This action cannot be undone.")
        .replace("##source", `<strong>${this.state.sourceName}</strong>`)
        .replace("##target", `<strong>${this.state.targetName}</strong>`);
      let dialogOptions = {
        title: t("Are you sure you want to copy permissions?"),
        message: finalMessage,
        labels: { ok: t("Import"), cancel: t("Cancel") },
        onok: () => {
          this.setState({ isAwaitingAssetChange: true });
          // disable button until it's done
          this.refreshImportButton();
          actions.permissions.copyPermissionsFrom(
            this.state.sourceUid,
            this.state.targetUid
          );
        },
        oncancel: () => {
          dialog.destroy();
        }
      };
      dialog.set(dialogOptions).show();
    }
  }

  render() {
    const importButtonClassName = classNames(
      "mdl-button",
      "mdl-js-button",
      "mdl-button--raised",
      this.state.sourceUid ? "mdl-button--colored" : "mdl-button--disabled"
    );

    const availableOptions = [];
    for (const assetUid in stores.allAssets.byUid) {
      if (stores.allAssets.byUid.hasOwnProperty(assetUid)) {
        // because choosing itself doesn't make sense
        if (assetUid !== this.state.targetUid) {
          availableOptions.push({
            value: assetUid,
            label: stores.allAssets.byUid[assetUid].name
          });
        }
      }
    }

    return (
      <bem.FormView__cell>
        {!this.state.isCopyFormVisible && (
          <bem.FormModal__item
            m="copy-team-permissions-opener"
            onClick={this.showCopyForm}
          >
            {t("Copy team from another project")}
          </bem.FormModal__item>
        )}
        {this.state.isCopyFormVisible && (
          <bem.FormView__cell>
            <bem.FormView__cell m="label">
              {t("Copy team and permissions from another project")}
            </bem.FormView__cell>
            <bem.FormModal__item>
              {t(
                "This will overwrite any existing sharing settings defined in this project."
              )}
            </bem.FormModal__item>
            <bem.FormModal__item m={["gray-row", "copy-team-permissions"]}>
              <Select
                id="teamPermissions"
                ref="sourceUid"
                value={this.state.sourceUid}
                clearable={false}
                placeholder={t("Select source project…")}
                options={availableOptions}
                onChange={this.updateTeamPermissionsInput}
              />
              <button
                className={importButtonClassName}
                disabled={!this.state.isImportButtonEnabled}
                onClick={this.safeCopyPermissionsFrom}
              >
                {t("import")}
              </button>
            </bem.FormModal__item>
          </bem.FormView__cell>
        )}
      </bem.FormView__cell>
    );
  }
}

reactMixin(CopyTeamPermissions.prototype, Reflux.ListenerMixin);

export default CopyTeamPermissions;
