import React from 'react/addons';
import Reflux from 'reflux';
import _ from 'underscore';
import {dataInterface} from '../dataInterface';
import {
  Navigation,
} from 'react-router';
import actions from '../actions';
import bem from '../bem';
import stores from '../stores';
import Select from 'react-select';
import ui from '../ui';
import mdl from '../libs/rest_framework/material';

import ReportViewItem from './reportViewItem';

import {
  assign,
  t,
  log,
} from '../utils';

function labelVal(label, value) {
  // returns {label: "Some Value", value: "some_value"} for react-select
  return {label: t(label), value: (value || label.toLowerCase().replace(/\W+/g, '_'))};
}
let reportStyles = [
  labelVal('Vertical'),
  labelVal('Donut'),
  labelVal('Area'),
  labelVal('Horizontal'),
  labelVal('Pie'),
  labelVal('Line'),
];

var DefaultChartTypePicker = React.createClass({
  defaultReportStyleChange (e) {
    this.props.onChange({
      default: true,
    }, {
      report_type: e.currentTarget.value || 'bar'
    });
  },
  render () {
    var radioButtons = reportStyles.map(function(style){
       return (
          <bem.GraphSettings__radio m={style.value}>
              <input type="radio" name="chart_type" 
                value={style.value} 
                checked={this.props.defaultStyle.report_type === style.value} 
                onChange={this.defaultReportStyleChange} 
                id={'type-' + style.value} />
              <label htmlFor={'type-' + style.value}>
                {style.label}
              </label>
          </bem.GraphSettings__radio>
       );
    }, this);

    return (
        <bem.GraphSettings__charttype>
          {radioButtons}
        </bem.GraphSettings__charttype>
      );
  },
});

let reportColorSets = [
  {
    label: 'set1', 
    colors: [
      'rgba(52, 106, 200, 0.8)',
      'rgba(252, 74, 124, 0.8)',
      'rgba(250, 213, 99, 0.8)',
      'rgba(113, 230, 33, 0.8)',
      'rgba(78, 203, 255, 0.8)',
      'rgba(253, 190, 76, 0.8)',
      'rgba(77, 124, 244, 0.8)',
      'rgba(33, 231, 184, 0.8)'
    ]
  },
  {
    label: 'set2', 
    colors: [
      'rgba(40, 106, 163, 0.8)',
      'rgba(69, 137, 197, 0.8)',
      'rgba(0, 123, 234, 0.8)',
      'rgba(0, 134, 255, 0.8)',
      'rgba(50, 159, 255, 0.8)',
      'rgba(100, 182, 255, 0.8)',
      'rgba(141, 200, 255, 0.8)',
      'rgba(192, 224, 255, 0.8)'
    ]
  },
  {
    label: 'set3', 
    colors: [
      'rgba(39, 69, 255, 0.8)',
      'rgba(34, 122, 233, 0.8)',
      'rgba(46, 145, 243, 0.8)',
      'rgba(92, 173, 255, 0.8)',
      'rgba(148, 200, 255, 0.8)',
      'rgba(31, 174, 228, 0.8)',
      'rgba(25, 214, 209, 0.8)',
      'rgba(28, 234, 225, 0.8)'
    ]
  },  
  {
    label: 'set4', 
    colors: [
      'rgba(253, 35, 4, 0.8)',
      'rgba(253, 104, 97, 0.8)',
      'rgba(232, 65, 14, 0.8)',
      'rgba(253, 146, 72, 0.8)',
      'rgba(233, 139, 3, 0.8)',
      'rgba(253, 215, 114, 0.8)',
      'rgba(254, 227, 159, 0.8)',
      'rgba(253, 146, 72, 0.8)'
    ]
  },
  {
    label: 'set5', 
    colors: [
      'rgba(63, 63, 63, 1)',
      'rgba(90, 90, 90, 1)',
      'rgba(107, 107, 107, 1)',
      'rgba(128, 128, 128, 1)',
      'rgba(151, 151, 151, 1)',
      'rgba(169, 169, 169, 1)',
      'rgba(196, 196, 196, 1)',
      'rgba(178, 179, 190, 1)'
    ]
  }
];

var DefaultChartColorsPicker = React.createClass({
  defaultReportColorsChange (e) {
    this.props.onChange({
      default: true,
    }, {
      report_colors: reportColorSets[e.currentTarget.value].colors || reportColorSets[0].colors
    });
  },
  render () {
    var radioButtons = reportColorSets.map(function(set, index){
       return (
          <bem.GraphSettings__radio>
              <input type="radio" name="chart_colors" 
                value={index} 
                checked={this.props.defaultStyle.report_colors === reportColorSets[index].colors} 
                onChange={this.defaultReportColorsChange} 
                id={'type-' + set.label} />
              <label htmlFor={'type-' + set.label}>
               {
                  reportColorSets[index].colors.map(function(color){
                       return (
                          <div style={{backgroundColor: color}}>
                          </div>
                       );
                    }, this)               
               }                
              </label>
          </bem.GraphSettings__radio>
       );
    }, this);

    return (
        <bem.GraphSettings__colors>
          {radioButtons}
        </bem.GraphSettings__colors>
      );
  },
});


var IndividualReportStylePicker = React.createClass({
  specificReportStyleChange (value) {
    this.props.onChange({
      kuid: this.props.row.$kuid,
    }, {
      report_type: value || false,
    });
  },
  render () {
    let kuid = this.props.row.$kuid;
    return (
        <div>
          <Select
            name={`report_type__${kuid}`}
            value={this.props.style.report_type}
            clearable={true}
            clearValueText={t('none')}
            placeholder={t('report type')}
            options={reportStyles}
            onChange={this.specificReportStyleChange}
          />
        </div>
      );
  },
});

var SizeSliderInput = React.createClass({
  getInitialState: function() {
    return {value: this.props.default};
  },
  handleChange: function(event) {
    this.props.onChange({
      value: event.target.value,
      id: this.props.name
    });

    this.setState({value: event.target.value});
  },
  render: function() {
    return (
      <div className="slider-item">
        <label> 
          {this.props.label}
          {this.state.value}
        </label>
        <input 
          className="mdl-slider mdl-js-slider"
          id={this.props.name}
          type="range" 
          min={this.props.min} 
          max={this.props.max}
          value={this.state.value} 
          onChange={this.handleChange}
          step="5" />
      </div>
    );
  },
});

var Reports = React.createClass({
  mixins: [
    Navigation,
    Reflux.ListenerMixin,
  ],
  componentDidMount () {
    let uid = this.props.params.assetid;
    // PM note: this below seems to cause child reportViewItem's componentWillUpdate to run twice, causing odd animation issues
    // this.listenTo(actions.reports.setStyle.completed, (asset)=>{
    //   if (asset.uid === uid) {
    //     this.setState({
    //       reportStyles: asset.report_styles,
    //     });
    //   }
    // });
    stores.allAssets.whenLoaded(uid, (asset)=>{
      let rowsByKuid = {};
      let kuids = [];
      let reportStyles = asset.report_styles;
      let defaultReportStyle = reportStyles.default;
      let specifiedReportStyles = reportStyles.specified;

      if (asset.content.survey != undefined) {
        asset.content.survey.forEach(function(r){
          let $kuid = r.$kuid,
            style = specifiedReportStyles[$kuid];
          r._reportStyle = style;
          rowsByKuid[r.$kuid] = r;
        });

        dataInterface.getReportData({uid: uid, kuids: kuids}).done((data)=>{

          var dataWithResponses = [];
          data.list.forEach(function(row){
            if (row.data.responses != undefined) {
              dataWithResponses.push(row);
            }
          });

          this.setState({
            asset: asset,
            rowsByKuid: rowsByKuid,
            reportStyles: asset.report_styles,
            reportData: dataWithResponses,
          });
        });
      } else {
        // Redundant?
        console.error('Survey not defined.');
      }
    });
  },
  getInitialState () {
    return {
      graphWidth: "700",
      graphHeight: "250",
      translationIndex: 0,
    };
  },
  reportStyleChange (params, value) {
    let assetUid = this.state.asset.uid;
    let sett_ = this.state.reportStyles;
    if (params.default) {
      assign(sett_.default, value);
    } else if (params.kuid) {
      let kuid = params.kuid;
      if (!sett_.specified[kuid]) {
        sett_.specified[kuid] = {};
      }
      assign(sett_.specified[kuid], value);
    }
    actions.reports.setStyle(assetUid, sett_);
    this.setState({
      reportStyles: sett_,
    });
  },
  reportSizeChange (params, value) {
    if (params.id == 'width') {
      this.setState({graphWidth: params.value});
    } else {
      this.setState({graphHeight: params.value});
    }
  },
  translationIndexChange (val) {
    this.setState({translationIndex: val});
  },
  toggleReportGraphSettings () {
    this.setState({
      showReportGraphSettings: !this.state.showReportGraphSettings,
    });
  },
  toggleExpandedReports () {
    stores.pageState.setDrawerHidden(!this.state.showExpandedReport);
    this.setState({
      showExpandedReport: !this.state.showExpandedReport,
    });
  },
  renderReportButtons () {
    return (
      <bem.FormView__reportButtons>
        <button className="mdl-button mdl-js-button"
                onClick={this.toggleReportGraphSettings}>
          {t('Graph Settings')}
        </button>
 
        <button className="mdl-button mdl-js-button"
                id="report-language">
          {t('Language')}
          <i className="fa fa-caret-down"></i>
        </button>
 
        <ul className="mdl-menu mdl-menu--bottom-right mdl-js-menu mdl-js-ripple-effect"
            htmlFor="report-language">
          <li>
            <a className="mdl-menu__item">
              {t('Test link 1')}
            </a>
          </li>
          <li>
            <a className="mdl-menu__item">
              {t('Test link 2')}
            </a>
          </li>
        </ul> 
 
        <button className="mdl-button mdl-js-button"
                id="report-groupby">
          {t('Group By')}
          <i className="fa fa-caret-down"></i>
        </button>
 
        <ul className="mdl-menu mdl-menu--bottom-right mdl-js-menu mdl-js-ripple-effect"
            htmlFor="report-groupby">
          <li>
            <a className="mdl-menu__item">
              {t('Test group link 1')}
            </a>
          </li>
          <li>
            <a className="mdl-menu__item">
              {t('Test group link 2')}
            </a>
          </li>
        </ul> 
 
        <button className="mdl-button mdl-js-button"
                id="report-viewall">
          {t('View All')}
          <i className="fa fa-caret-down"></i>
        </button>
 
        <ul className="mdl-menu mdl-menu--bottom-right mdl-js-menu mdl-js-ripple-effect"
            htmlFor="report-viewall">
          <li>
            <a className="mdl-menu__item">
              {t('Test view all 1')}
            </a>
          </li>
          <li>
            <a className="mdl-menu__item">
              {t('Test view all 2')}
            </a>
          </li>
        </ul> 
 
        <button className="mdl-button mdl-js-button mdl-button--icon report-button__expand"
                onClick={this.toggleExpandedReports} data-tip={t('Expand')}>
          <i className="k-icon-expand" />
        </button>
 
        <button className="mdl-button mdl-js-button mdl-button--icon report-button__print" data-tip={t('Print')}>
          <i className="k-icon-print" />
        </button>
 
      </bem.FormView__reportButtons>
    );
  },
  renderReportGraphSettings () {
    let asset = this.state.asset,
        rowsByKuid = this.state.rowsByKuid,
        explicitStyles,
        explicitStylesList = [],
        defaultStyle;
    if (asset && asset.content) {
      explicitStyles = this.state.reportStyles.specified || {};
      defaultStyle = this.state.reportStyles.default || {};
    }

    let translations = false;
    let reportData = this.state.reportData || [];

    for (var i = reportData.length - 1; i >= 0; i--) {;
      reportData[i].style = defaultStyle;
    }
    return (
      <bem.GraphSettings>
        <div className="mdl-tabs mdl-js-tabs mdl-js-ripple-effect">
          <div className="mdl-tabs__tab-bar">
              <a href="#graph-type" className="mdl-tabs__tab is-active">
                {t('Chart Type')}
              </a>
              <a href="#graph-colors" className="mdl-tabs__tab">
                {t('Colors')}
              </a>
              <a href="#graph-labels" className="mdl-tabs__tab">
                {t('Size')}
              </a>
          </div>
 
          <div className="mdl-tabs__panel is-active" id="graph-type">
            <DefaultChartTypePicker
                defaultStyle={defaultStyle}
                onChange={this.reportStyleChange}
                translationIndex={this.state.translationIndex}
              />
          </div>
          <div className="mdl-tabs__panel" id="graph-colors">
            <DefaultChartColorsPicker
                defaultStyle={defaultStyle}
                onChange={this.reportStyleChange}
                translationIndex={this.state.translationIndex}
              />
          </div>
          <div className="mdl-tabs__panel graph-tab__size" id="graph-labels">
            <SizeSliderInput 
                        name="width" min="300" max="900" default={this.state.graphWidth} 
                        label={t('Width: ')} 
                        onChange={this.reportSizeChange} />
            <div className="is-edge">
              <SizeSliderInput 
                        name="height" min="200" max="500" default={this.state.graphHeight}
                        label={t('Height: ')} 
                        onChange={this.reportSizeChange} />
            </div>
          </div>
        </div>
 
        <bem.GraphSettings__buttons>
          <button className="mdl-button mdl-js-button primary"
                  onClick={this.toggleReportGraphSettings}>
            {t('Done')}
          </button>
        </bem.GraphSettings__buttons>
      </bem.GraphSettings>
    );
  },
  render () {
    let asset = this.state.asset,
        rowsByKuid = this.state.rowsByKuid,
        explicitStyles,
        explicitStylesList = [],
        defaultStyle;
    if (asset && asset.content) {
      explicitStyles = this.state.reportStyles.specified || {};
      defaultStyle = this.state.reportStyles.default || {};

      defaultStyle.graphWidth = this.state.graphWidth;
      defaultStyle.graphHeight = this.state.graphHeight;
    }

    let translations = false;
    let reportData = this.state.reportData || [];

    for (var i = reportData.length - 1; i >= 0; i--) {;
      reportData[i].style = defaultStyle;
    }

    return (
        <bem.ReportView>
          {this.renderReportButtons()}
          {this.state.asset ?
            <div>
              {
                translations ?
                  <Select
                      name={`translation-switcher`}
                      value={this.state.translationIndex}
                      clearable={false}
                      default={0}
                      placeholder={t('Translation')}
                      options={translations}
                      onChange={this.translationIndexChange}
                    />
                : null
              }
              <bem.ReportView__wrap>
                <bem.ReportView__warning>
                  <h4>{t('Warning')}</h4>
                  <p>{t('This is an automated report based on raw data submitted to this project. Please conduct proper data cleaning prior to using the graphs and figures used on this page. ')}</p>
                </bem.ReportView__warning>
                {
                  reportData.length === 0 ?
                    <p>No report data</p>
                  :
                  reportData.map((rowContent)=>{
                    let kuid = rowContent.$kuid;
                    return (
                        <bem.ReportView__item title={rowContent.$kuid}>
                          {/* style picker:
                          <IndividualReportStylePicker key={kuid}
                              row={row}
                              onChange={this.reportStyleChange}
                              translationIndex={this.state.translationIndex}
                              asset={asset}
                              style={row.chartStyle}
                            />
                          */}
                          <ReportViewItem {...rowContent} />
                        </bem.ReportView__item>
                      );
                  })
                }
              </bem.ReportView__wrap>
            </div>
          :
            <bem.Loading>
              <bem.Loading__inner>
                <i />
                {t('loading...')}
              </bem.Loading__inner>
            </bem.Loading>
          }
          {this.state.showReportGraphSettings ?
            <ui.Modal open onClose={this.toggleReportGraphSettings} title={t('Global Graph Settings')}>
              <ui.Modal.Body>
                {this.renderReportGraphSettings()}
              </ui.Modal.Body>
            </ui.Modal>
 
          : null}
        </bem.ReportView>
      );
  },
  componentDidUpdate() {
    mdl.upgradeDom();
  }

})

export default Reports;
